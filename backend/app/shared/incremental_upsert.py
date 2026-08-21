"""Motor de importação incremental (insert / ignore / update).

Porte literal de `src/importers/shared/incremental-upsert.ts`.

Regra central: registro ausente -> insere; idêntico (mesmo contentHash) ->
ignora; mudou -> atualiza SOMENTE aquele registro. Nunca apaga o resto do mês
— a ausência de um registro numa nova importação não implica remoção.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

__all__ = [
    "IncrementalRecord",
    "UpsertError",
    "UpsertOutcome",
    "RecordDelegate",
    "process_incremental_batch",
]


@dataclass(frozen=True, slots=True)
class IncrementalRecord:
    business_key: str
    content_hash: str
    data: dict[str, Any]


@dataclass(slots=True)
class UpsertError:
    business_key: str
    message: str


@dataclass(slots=True)
class UpsertOutcome:
    inserted: int = 0
    ignored: int = 0
    updated: int = 0
    rejected: int = 0
    errors: list[UpsertError] = field(default_factory=list)


class RecordDelegate(Protocol):
    """Delegate mínimo que um repositório de módulo precisa fornecer. Mantém
    o motor desacoplado do SQLAlchemy para permitir testes com mocks.

    `find_by_business_key` retorna diretamente a string `contentHash` do
    registro existente (ou `None` se não existir) — de propósito, para que
    nenhuma implementação de módulo precise expor um objeto com um atributo
    chamado exatamente `content_hash` (os modelos ORM usam `contentHash`,
    camelCase, para espelhar as colunas reais do Postgres)."""

    async def find_by_business_key(self, business_key: str) -> str | None: ...

    async def insert(self, record: IncrementalRecord, import_id: str) -> None: ...

    async def update(self, record: IncrementalRecord, import_id: str) -> None: ...


async def process_incremental_batch(
    records: list[IncrementalRecord], delegate: RecordDelegate, import_id: str
) -> UpsertOutcome:
    """Deve ser chamado dentro de uma transação pelo serviço do módulo."""
    outcome = UpsertOutcome()

    for record in records:
        try:
            existing_content_hash = await delegate.find_by_business_key(record.business_key)
            if existing_content_hash is None:
                await delegate.insert(record, import_id)
                outcome.inserted += 1
            elif existing_content_hash == record.content_hash:
                outcome.ignored += 1
            else:
                await delegate.update(record, import_id)
                outcome.updated += 1
        except Exception as exc:  # noqa: BLE001 — erro por linha não deve abortar o lote
            outcome.rejected += 1
            outcome.errors.append(UpsertError(business_key=record.business_key, message=str(exc)))

    return outcome
