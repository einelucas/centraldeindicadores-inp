"""Testes de `app/modules/imports/bulk_upsert.py` contra o Postgres real —
usa `RdoRecord` como tabela de exemplo (mesmo contrato dos outros 3 módulos).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.models.records import RdoRecord
from app.modules.imports.bulk_upsert import bulk_upsert
from app.shared.incremental_upsert import IncrementalRecord

_MUTABLE_COLUMNS = ("contentHash", "statusDescricao", "raw", "lastImportId")


def _insert_row(record: IncrementalRecord, import_id: str) -> dict[str, Any]:
    data = record.data
    return {
        "businessKey": record.business_key,
        "contentHash": record.content_hash,
        "dataReferencia": data["dataReferencia"],
        "empresaNome": data["empresaNome"],
        "statusDescricao": data["statusDescricao"],
        "relatorioId": data.get("relatorioId"),
        "grupo": data.get("grupo"),
        "disciplina": data.get("disciplina"),
        "year": data["year"],
        "month": data["month"],
        "raw": data.get("raw", {}),
        "firstImportId": import_id,
        "lastImportId": import_id,
    }


def _record(key: str, status: str = "Aprovado") -> IncrementalRecord:
    return IncrementalRecord(
        business_key=key,
        content_hash=f"hash-{status}",
        data={
            "dataReferencia": datetime(2026, 6, 1),
            "empresaNome": "RDN",
            "statusDescricao": status,
            "relatorioId": key,
            "grupo": None,
            "disciplina": None,
            "year": 2026,
            "month": 6,
            "raw": {},
        },
    )


async def test_inserts_new_records(db_session) -> None:
    outcome = await bulk_upsert(
        db_session, RdoRecord, [_record("k1"), _record("k2")],
        import_id="job-1", build_insert_row=_insert_row, mutable_columns=_MUTABLE_COLUMNS,
    )
    assert outcome.inserted == 2
    assert outcome.updated == 0
    assert outcome.ignored == 0

    rows = (await db_session.execute(select(RdoRecord).order_by(RdoRecord.businessKey))).scalars().all()
    assert [r.businessKey for r in rows] == ["k1", "k2"]


async def test_ignores_unchanged_record_on_reimport(db_session) -> None:
    record = _record("k1")
    await bulk_upsert(
        db_session, RdoRecord, [record],
        import_id="job-1", build_insert_row=_insert_row, mutable_columns=_MUTABLE_COLUMNS,
    )
    outcome = await bulk_upsert(
        db_session, RdoRecord, [record],
        import_id="job-2", build_insert_row=_insert_row, mutable_columns=_MUTABLE_COLUMNS,
    )
    assert outcome.inserted == 0
    assert outcome.updated == 0
    assert outcome.ignored == 1

    row = (await db_session.execute(select(RdoRecord).where(RdoRecord.businessKey == "k1"))).scalar_one()
    assert row.lastImportId == "job-1"  # nunca tocado no reenvio ignorado


async def test_updates_record_with_changed_content_hash(db_session) -> None:
    await bulk_upsert(
        db_session, RdoRecord, [_record("k1", status="Preenchendo Relatório")],
        import_id="job-1", build_insert_row=_insert_row, mutable_columns=_MUTABLE_COLUMNS,
    )
    outcome = await bulk_upsert(
        db_session, RdoRecord, [_record("k1", status="Aprovado")],
        import_id="job-2", build_insert_row=_insert_row, mutable_columns=_MUTABLE_COLUMNS,
    )
    assert outcome.inserted == 0
    assert outcome.updated == 1
    assert outcome.ignored == 0

    row = (await db_session.execute(select(RdoRecord).where(RdoRecord.businessKey == "k1"))).scalar_one()
    assert row.statusDescricao == "Aprovado"
    assert row.lastImportId == "job-2"


async def test_mixed_batch_insert_update_ignore(db_session) -> None:
    await bulk_upsert(
        db_session, RdoRecord, [_record("keep"), _record("change", status="Preenchendo Relatório")],
        import_id="job-1", build_insert_row=_insert_row, mutable_columns=_MUTABLE_COLUMNS,
    )
    outcome = await bulk_upsert(
        db_session, RdoRecord,
        [_record("keep"), _record("change", status="Aprovado"), _record("new")],
        import_id="job-2", build_insert_row=_insert_row, mutable_columns=_MUTABLE_COLUMNS,
    )
    assert outcome.inserted == 1
    assert outcome.updated == 1
    assert outcome.ignored == 1


async def test_respects_small_chunk_size_across_multiple_rounds(db_session) -> None:
    records = [_record(f"k{i}") for i in range(5)]
    outcome = await bulk_upsert(
        db_session, RdoRecord, records,
        import_id="job-1", build_insert_row=_insert_row, mutable_columns=_MUTABLE_COLUMNS,
        chunk_size=2,
    )
    assert outcome.inserted == 5
    count = (await db_session.execute(select(RdoRecord))).scalars().all()
    assert len(count) == 5


async def test_empty_records_is_a_noop(db_session) -> None:
    outcome = await bulk_upsert(
        db_session, RdoRecord, [],
        import_id="job-1", build_insert_row=_insert_row, mutable_columns=_MUTABLE_COLUMNS,
    )
    assert outcome.inserted == 0
    assert outcome.updated == 0
    assert outcome.ignored == 0
