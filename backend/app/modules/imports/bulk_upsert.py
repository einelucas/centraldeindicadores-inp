"""Upsert em lote para o fluxo de upload de arquivos (`POST
/importacoes/{modulo}/arquivos`).

Substitui, só para esse fluxo novo, o loop linha-a-linha de
`app/shared/incremental_upsert.py::process_incremental_batch` (que continua
existindo e sendo usado pelas rotas antigas `/importacoes/{id}/lotes`,
enquanto RNC/5S/IDP não migram — ver plano de fases). Por chunk de
`chunk_size` `IncrementalRecord`:

1. Uma única `SELECT businessKey, contentHash WHERE businessKey = ANY(...)`.
2. Classificação em memória: sem match -> insert; mesmo `contentHash` ->
   ignore (nem entra no upsert); hash diferente -> update.
3. Um único `INSERT ... ON CONFLICT (businessKey) DO UPDATE` cobrindo todos
   os inserts+updates do chunk — o Postgres decide linha a linha via
   `ON CONFLICT`, mas o Python já sabe de antemão quem é quem para reportar
   os totais corretamente.

Genérico o bastante para os 4 módulos — só muda o `model` SQLAlchemy, como
montar a linha de insert (`build_insert_row`) e quais colunas são mutáveis
no update (`mutable_columns`).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.incremental_upsert import IncrementalRecord

__all__ = ["BulkUpsertOutcome", "bulk_upsert"]

_DEFAULT_CHUNK_SIZE = 750


@dataclass(slots=True)
class BulkUpsertOutcome:
    inserted: int = 0
    updated: int = 0
    ignored: int = 0


async def bulk_upsert(
    session: AsyncSession,
    model: type[Any],
    records: list[IncrementalRecord],
    *,
    import_id: str,
    build_insert_row: Callable[[IncrementalRecord, str], dict[str, Any]],
    mutable_columns: Sequence[str],
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
) -> BulkUpsertOutcome:
    """`build_insert_row(record, import_id)` devolve o dict completo de
    colunas para um INSERT novo (inclui `businessKey`/`contentHash`,
    `firstImportId`/`lastImportId` e os campos de dados — nunca `id`,
    `firstSeenAt`/`createdAt`, que ficam a cargo dos defaults da coluna).
    `mutable_columns` lista, dentre essas mesmas chaves, quais entram no
    `DO UPDATE SET` (tipicamente `contentHash` + campos de conteúdo +
    `lastImportId` — nunca campos que compõem a `businessKey`, tratados como
    identidade imutável)."""
    outcome = BulkUpsertOutcome()
    business_key_col = model.businessKey
    content_hash_col = model.contentHash

    for offset in range(0, len(records), chunk_size):
        chunk = records[offset : offset + chunk_size]
        keys = [record.business_key for record in chunk]

        existing = await session.execute(
            select(business_key_col, content_hash_col).where(business_key_col.in_(keys))
        )
        existing_hashes: dict[str, str] = {row[0]: row[1] for row in existing.all()}

        rows_to_write: list[dict[str, Any]] = []
        for record in chunk:
            current_hash = existing_hashes.get(record.business_key)
            if current_hash is None:
                outcome.inserted += 1
                rows_to_write.append(build_insert_row(record, import_id))
            elif current_hash == record.content_hash:
                outcome.ignored += 1
            else:
                outcome.updated += 1
                rows_to_write.append(build_insert_row(record, import_id))

        if not rows_to_write:
            continue

        now = datetime.now(UTC).replace(tzinfo=None)
        stmt = pg_insert(model).values(rows_to_write)
        set_: dict[str, Any] = {column: stmt.excluded[column] for column in mutable_columns}
        set_["lastSeenAt"] = now
        set_["updatedAt"] = now
        stmt = stmt.on_conflict_do_update(index_elements=["businessKey"], set_=set_)
        await session.execute(stmt)

    return outcome
