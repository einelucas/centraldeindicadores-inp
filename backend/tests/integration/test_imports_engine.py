"""Testes de integração do motor de importação genérico (Postgres real).

Usa um módulo fictício ("test-module") registrado só para este teste,
apoiado na tabela `RdoRecord` (ainda sem router de negócio próprio neste
ponto da suíte) apenas como armazenamento de destino do delegate — não testa
nenhuma regra do módulo RDO em si, só o motor genérico
(ImportJob/ImportBatch/idempotência/sub-lotes) exercitado via HTTP real.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.records import RdoRecord
from app.modules.imports.registry import ModuleDefinition, register_module
from app.shared.hashing import make_business_key, make_content_hash
from app.shared.incremental_upsert import IncrementalRecord


class _FakeDelegate:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_by_business_key(self, business_key: str) -> str | None:
        result = await self.session.execute(
            select(RdoRecord.contentHash).where(RdoRecord.businessKey == business_key)
        )
        return result.scalar_one_or_none()

    async def insert(self, record: IncrementalRecord, import_id: str) -> None:
        data = record.data
        self.session.add(
            RdoRecord(
                businessKey=record.business_key,
                contentHash=record.content_hash,
                dataReferencia=datetime.fromisoformat(data["dataReferencia"]),
                empresaNome=data["empresaNome"],
                statusDescricao=data["statusDescricao"],
                year=data["year"],
                month=data["month"],
                raw=data,
                firstImportId=import_id,
                lastImportId=import_id,
            )
        )
        await self.session.flush()

    async def update(self, record: IncrementalRecord, import_id: str) -> None:
        result = await self.session.execute(
            select(RdoRecord).where(RdoRecord.businessKey == record.business_key)
        )
        existing = result.scalar_one()
        existing.contentHash = record.content_hash
        existing.statusDescricao = record.data["statusDescricao"]
        existing.raw = record.data
        existing.lastImportId = import_id
        await self.session.flush()


def _to_incremental_records(raw_records: list[dict[str, Any]]) -> tuple[list[IncrementalRecord], int]:
    records: list[IncrementalRecord] = []
    rejected = 0
    for item in raw_records:
        try:
            business_key = make_business_key("TESTMOD", [item["relatorioId"]])
            content_hash = make_content_hash({"statusDescricao": item["statusDescricao"]})
            records.append(
                IncrementalRecord(business_key=business_key, content_hash=content_hash, data=item)
            )
        except KeyError:
            rejected += 1
    return records, rejected


async def _noop_recalc(session: AsyncSession) -> None:
    return None


register_module(
    "test-module",
    ModuleDefinition(
        to_incremental_records=_to_incremental_records,
        delegate_factory=_FakeDelegate,
        recalc_indicators=_noop_recalc,
    ),
)


def _record(relatorio_id: str, status: str) -> dict[str, Any]:
    return {
        "relatorioId": relatorio_id,
        "dataReferencia": "2026-01-05T00:00:00",
        "empresaNome": "UNIDADE A",
        "statusDescricao": status,
        "year": 2026,
        "month": 1,
    }


async def test_full_import_flow_insert_ignore_update(client, auth_header) -> None:
    start = await client.post(
        "/api/v1/importacoes/iniciar",
        json={
            "module": "test-module",
            "fileName": "arquivo.xlsx",
            "totalFound": 2,
        },
        headers=auth_header("ANALYST"),
    )
    assert start.status_code == 200
    job_id = start.json()["importJobId"]
    assert start.json()["status"] == "PROCESSING"

    batch_payload = {
        "batchNumber": 1,
        "records": [_record("R1", "Aprovado"), _record("R2", "Revisar Relatório")],
    }
    first = await client.post(
        f"/api/v1/importacoes/{job_id}/lotes", json=batch_payload, headers=auth_header("ANALYST")
    )
    assert first.status_code == 200
    body = first.json()
    assert body["inserted"] == 2
    assert body["ignored"] == 0
    assert body["updated"] == 0
    assert body["alreadyProcessed"] is False

    # Reenviar o MESMO lote (mesmo batchNumber) deve ser idempotente.
    replay = await client.post(
        f"/api/v1/importacoes/{job_id}/lotes", json=batch_payload, headers=auth_header("ANALYST")
    )
    assert replay.status_code == 200
    assert replay.json()["alreadyProcessed"] is True
    assert replay.json()["inserted"] == 2  # devolve os totais já persistidos, não reprocessa

    # Um segundo lote com R1 alterado (update) e um registro novo (insert).
    second_batch = {
        "batchNumber": 2,
        "records": [_record("R1", "Aprovado"), _record("R3", "Aprovado")],
    }
    # R1 já está "Aprovado" (sem mudança) -> ignored; R3 é novo -> inserted.
    second = await client.post(
        f"/api/v1/importacoes/{job_id}/lotes", json=second_batch, headers=auth_header("ANALYST")
    )
    assert second.status_code == 200
    assert second.json()["inserted"] == 1
    assert second.json()["ignored"] == 1

    finalize = await client.post(
        f"/api/v1/importacoes/{job_id}/finalizar", headers=auth_header("ANALYST")
    )
    assert finalize.status_code == 200
    totals = finalize.json()["totals"]
    assert totals["inserted"] == 3
    assert totals["ignored"] == 1
    assert finalize.json()["status"] == "COMPLETED"

    detail = await client.get(f"/api/v1/importacoes/{job_id}", headers=auth_header("ANALYST"))
    assert detail.status_code == 200
    assert len(detail.json()["batches"]) == 2

    errors = await client.get(f"/api/v1/importacoes/{job_id}/erros", headers=auth_header("ANALYST"))
    assert errors.status_code == 200
    assert errors.json()["items"] == []


async def test_update_changes_content_hash(client, auth_header) -> None:
    start = await client.post(
        "/api/v1/importacoes/iniciar",
        json={"module": "test-module", "fileName": "a.xlsx", "totalFound": 1},
        headers=auth_header("ANALYST"),
    )
    job_id = start.json()["importJobId"]

    await client.post(
        f"/api/v1/importacoes/{job_id}/lotes",
        json={"batchNumber": 1, "records": [_record("R9", "Preenchendo Relatório")]},
        headers=auth_header("ANALYST"),
    )

    updated = await client.post(
        f"/api/v1/importacoes/{job_id}/lotes",
        json={"batchNumber": 2, "records": [_record("R9", "Aprovado")]},
        headers=auth_header("ANALYST"),
    )
    assert updated.json()["updated"] == 1
    assert updated.json()["inserted"] == 0


async def test_unregistered_module_returns_400_on_start(client, auth_header) -> None:
    response = await client.post(
        "/api/v1/importacoes/iniciar",
        json={"module": "nao-existe", "fileName": "a.xlsx", "totalFound": 0},
        headers=auth_header("ANALYST"),
    )
    assert response.status_code == 422  # DomainError -> 422 nesta API (ver decisions.md)


async def test_unknown_job_returns_404(client, auth_header) -> None:
    response = await client.get(
        "/api/v1/importacoes/00000000-0000-0000-0000-000000000000", headers=auth_header("ANALYST")
    )
    assert response.status_code == 404


async def test_viewer_cannot_run_import(client, auth_header) -> None:
    response = await client.post(
        "/api/v1/importacoes/iniciar",
        json={"module": "test-module", "fileName": "a.xlsx", "totalFound": 0},
        headers=auth_header("VIEWER"),
    )
    assert response.status_code == 403
