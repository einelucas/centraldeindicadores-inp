"""Testes de integração HTTP do módulo RDO, contra Postgres real."""

from __future__ import annotations

from sqlalchemy import select

from app.models.records import RdoRecord


async def _import_records(client, auth_header, records: list[dict], batch_number: int = 1) -> str:
    start = await client.post(
        "/api/v1/importacoes/iniciar",
        json={"module": "rdo", "fileName": "planilha.xlsx", "totalFound": len(records)},
        headers=auth_header("ANALYST"),
    )
    assert start.status_code == 200
    job_id = start.json()["importJobId"]

    batch = await client.post(
        f"/api/v1/importacoes/{job_id}/lotes",
        json={"batchNumber": batch_number, "records": records},
        headers=auth_header("ANALYST"),
    )
    assert batch.status_code == 200, batch.text

    finalize = await client.post(
        f"/api/v1/importacoes/{job_id}/finalizar", headers=auth_header("ANALYST")
    )
    assert finalize.status_code == 200
    return job_id


def _rdo_row(relatorio_id: str, status: str, empresa: str = "UNIDADE A", day: int = 5) -> dict:
    return {
        "dataReferencia": f"2027-03-{day:02d}T00:00:00",
        "empresaNome": empresa,
        "statusDescricao": status,
        "relatorioId": relatorio_id,
        "grupo": "Mecânica",
        "disciplina": "Tubulação",
        "year": 2027,
        "month": 3,
        "raw": {"responsavel": "João"},
    }


async def test_import_then_get_rdo(client, auth_header) -> None:
    records = [
        _rdo_row("R1", "Aprovado", day=1),
        _rdo_row("R2", "Aprovado", day=2),
        _rdo_row("R3", "Revisar Relatório", day=3),
        _rdo_row("R4", "Preenchendo Relatório", day=4),
    ]
    await _import_records(client, auth_header, records)

    response = await client.get("/api/v1/rdo?ano=2027&mes=3", headers=auth_header("VIEWER"))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 4
    assert body["result"]["totalEmitidos"] == 4
    assert body["result"]["totalAprovados"] == 2


async def test_reimport_is_idempotent(client, auth_header, db_session) -> None:
    records = [_rdo_row("R1", "Aprovado")]
    await _import_records(client, auth_header, records)
    await _import_records(client, auth_header, records, batch_number=2)

    result = await db_session.execute(select(RdoRecord))
    assert len(result.scalars().all()) == 1


async def test_patch_excluded_units_requires_import_run(client, auth_header) -> None:
    forbidden = await client.patch(
        "/api/v1/rdo", json={"excludedUnits": ["LEM"]}, headers=auth_header("VIEWER")
    )
    assert forbidden.status_code == 403

    ok = await client.patch(
        "/api/v1/rdo", json={"excludedUnits": ["lem", "lem"]}, headers=auth_header("ANALYST")
    )
    assert ok.status_code == 200
    assert ok.json()["excludedUnits"] == ["LEM"]


async def test_edit_status_requires_admin_and_recalculates(client, auth_header, db_session) -> None:
    await _import_records(client, auth_header, [_rdo_row("R1", "Revisar Relatório")])

    result = await db_session.execute(select(RdoRecord))
    record = result.scalars().one()

    forbidden = await client.patch(
        "/api/v1/rdo/registros",
        json={"id": record.id, "status": "Aprovado"},
        headers=auth_header("ANALYST"),
    )
    assert forbidden.status_code == 403

    ok = await client.patch(
        "/api/v1/rdo/registros",
        json={"id": record.id, "status": "Aprovado"},
        headers=auth_header("ADMIN"),
    )
    assert ok.status_code == 200
    assert ok.json()["updated"]["statusDescricao"] == "Aprovado"

    # No-op edit (mesmo status) -> unchanged, sem erro.
    noop = await client.patch(
        "/api/v1/rdo/registros",
        json={"id": record.id, "status": "Aprovado"},
        headers=auth_header("ADMIN"),
    )
    assert noop.status_code == 200
    assert noop.json()["unchanged"] is True


async def test_delete_registros_all_modes(client, auth_header) -> None:
    await _import_records(
        client, auth_header, [_rdo_row("R1", "Aprovado", day=1), _rdo_row("R2", "Aprovado", day=2)]
    )

    count = await client.get("/api/v1/rdo/registros", headers=auth_header("ADMIN"))
    assert count.status_code == 200
    assert count.json()["count"] == 2

    delete_all = await client.request(
        "DELETE", "/api/v1/rdo/registros", json={"all": True}, headers=auth_header("ADMIN")
    )
    assert delete_all.status_code == 200
    assert delete_all.json()["deleted"] == 2

    delete_again = await client.request(
        "DELETE", "/api/v1/rdo/registros", json={"all": True}, headers=auth_header("ADMIN")
    )
    assert delete_again.json()["deleted"] == 0


async def test_publish_creates_version_and_deactivates_previous(client, auth_header) -> None:
    await _import_records(client, auth_header, [_rdo_row("R1", "Aprovado")])

    # Período de um semestre operacional inteiro que cobre março/2027 (mês
    # usado por `_rdo_row`): S1 2027 = Dez/2026-Mai/2027. Só um período que
    # bate exatamente com um ciclo faz `historyCount` contar a publicação
    # (ver `resolve_publication_cycle`); sem período, a publicação nunca é
    # "resolvível" e não entra na contagem.
    cycle_body = {
        "threshold": 80,
        "periodStartYear": 2026,
        "periodStartMonth": 12,
        "periodEndYear": 2027,
        "periodEndMonth": 5,
    }

    first = await client.post("/api/v1/publicacoes/rdo", json=cycle_body, headers=auth_header("ADMIN"))
    assert first.status_code == 200
    assert first.json()["publication"]["version"] == 1
    assert first.json()["publication"]["payload"]["resultado"] == 100

    await _import_records(client, auth_header, [_rdo_row("R2", "Revisar Relatório")], batch_number=2)

    second = await client.post("/api/v1/publicacoes/rdo", json=cycle_body, headers=auth_header("ADMIN"))
    assert second.status_code == 200
    assert second.json()["publication"]["version"] == 2

    get_response = await client.get(
        "/api/v1/publicacoes/rdo"
        "?periodStartYear=2026&periodStartMonth=12&periodEndYear=2027&periodEndMonth=5",
        headers=auth_header("VIEWER"),
    )
    assert get_response.status_code == 200
    assert get_response.json()["publication"]["version"] == 2
    assert get_response.json()["historyCount"] >= 1


async def test_publish_without_records_is_domain_error(client, auth_header) -> None:
    response = await client.post(
        "/api/v1/publicacoes/rdo", json={"threshold": 80}, headers=auth_header("ADMIN")
    )
    assert response.status_code == 422


async def test_viewer_cannot_publish(client, auth_header) -> None:
    await _import_records(client, auth_header, [_rdo_row("R1", "Aprovado")])
    response = await client.post(
        "/api/v1/publicacoes/rdo", json={"threshold": 80}, headers=auth_header("VIEWER")
    )
    assert response.status_code == 403
