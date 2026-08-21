"""Testes de integração HTTP do módulo IDP/RSO, contra Postgres real."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.models.indicators import IndicatorResult
from app.models.records import IdpRsoRecord


async def _import_records(client, auth_header, records: list[dict], batch_number: int = 1) -> str:
    start = await client.post(
        "/api/v1/importacoes/iniciar",
        json={"module": "idp", "fileName": "rsos.zip", "totalFound": len(records)},
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


def _idp_row(
    *,
    unit: str = "Nova Mutum",
    rso_numero: int = 34,
    year: int = 2026,
    month: int = 6,
    civil_prev: float = 100.0,
    civil_real: float = 99.5,
    fase_prev: float = 53.08,
    fase_real: float = 54.79,
    reference_source: str = "PDF_MES_REF",
    reference_adjusted: bool = False,
) -> dict[str, Any]:
    return {
        "unit": unit, "detectedUnit": unit, "unitAdjusted": False,
        "rsoNumero": rso_numero, "detectedRsoNumero": rso_numero, "rsoAdjusted": False,
        "referenceYear": year, "referenceMonth": month,
        "detectedReferenceYear": year, "detectedReferenceMonth": month,
        "referenceSource": reference_source,
        "referenceOriginalText": f"Mês ref.: {month:02d}/{year}",
        "referenceAdjusted": reference_adjusted,
        "periodStart": None, "periodEnd": None, "emissionDate": None,
        "fileName": f"RSO {rso_numero}.pdf",
        "areas": ["Pipe Rack"],
        "discData": {"01 - Civil": [{"area": "Pipe Rack", "prevAcum": civil_prev, "realAcum": civil_real}]},
        "execucaoFases": [{"label": "Fase 1", "prevAcum": fase_prev, "realAcum": fase_real}],
        "raw": {},
    }


async def _indicator_results(db_session) -> list[IndicatorResult]:
    result = await db_session.execute(select(IndicatorResult).where(IndicatorResult.module == "idp"))
    return list(result.scalars().all())


async def test_import_then_get_idp_selects_latest_rso(client, auth_header) -> None:
    await _import_records(
        client, auth_header,
        [_idp_row(rso_numero=32, fase_prev=50, fase_real=45), _idp_row(rso_numero=34)],
    )

    response = await client.get(
        "/api/v1/idp?periodStartYear=2026&periodStartMonth=6&periodEndYear=2026&periodEndMonth=6",
        headers=auth_header("VIEWER"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2  # os 2 RSOs continuam no banco
    assert body["result"]["activeDocuments"] == 1  # só 1 unidade vence
    assert body["result"]["unitRows"][0]["rsoNumero"] == 34

    docs_by_rso = {d["rsoNumero"]: d for d in body["documents"]}
    assert docs_by_rso[34]["active"] is True
    assert docs_by_rso[32]["active"] is False  # continua no histórico, não venceu


async def test_unit_normalization_at_version_selection(client, auth_header) -> None:
    await _import_records(
        client, auth_header,
        [
            _idp_row(unit="RIO VERDE", rso_numero=37, fase_prev=50, fase_real=40),
            _idp_row(unit="Rio Verde", rso_numero=38),
        ],
    )

    response = await client.get(
        "/api/v1/idp?periodStartYear=2026&periodStartMonth=6&periodEndYear=2026&periodEndMonth=6",
        headers=auth_header("VIEWER"),
    )
    body = response.json()
    assert body["result"]["activeDocuments"] == 1  # RIO VERDE e Rio Verde colapsam
    assert body["result"]["unitRows"][0]["rsoNumero"] == 38


async def test_reimport_is_idempotent(client, auth_header, db_session) -> None:
    record = _idp_row()
    await _import_records(client, auth_header, [record])
    await _import_records(client, auth_header, [record], batch_number=2)

    result = await db_session.execute(select(IdpRsoRecord))
    assert len(result.scalars().all()) == 1


async def test_correction_updates_same_row_instead_of_duplicating(client, auth_header, db_session) -> None:
    await _import_records(client, auth_header, [_idp_row(reference_source="PDF_MES_REF")])
    await _import_records(
        client, auth_header,
        [_idp_row(month=7, reference_source="MANUAL", reference_adjusted=True)],
        batch_number=2,
    )

    rows = (await db_session.execute(select(IdpRsoRecord))).scalars().all()
    assert len(rows) == 1
    assert rows[0].referenceMonth == 7
    assert rows[0].referenceSource == "MANUAL"


async def test_registros_count_requires_admin(client, auth_header) -> None:
    await _import_records(client, auth_header, [_idp_row(rso_numero=32), _idp_row(rso_numero=34)])

    forbidden = await client.get("/api/v1/idp/registros", headers=auth_header("ANALYST"))
    assert forbidden.status_code == 403

    ok = await client.get("/api/v1/idp/registros", headers=auth_header("ADMIN"))
    assert ok.status_code == 200
    assert ok.json()["count"] == 2


async def test_delete_all_removes_rsos_and_indicator_results(client, auth_header, db_session) -> None:
    await _import_records(client, auth_header, [_idp_row()])
    assert len(await _indicator_results(db_session)) == 1

    deleted = await client.request(
        "DELETE", "/api/v1/idp/registros", json={"all": True}, headers=auth_header("ADMIN")
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 1

    remaining = (await db_session.execute(select(IdpRsoRecord))).scalars().all()
    assert remaining == []
    assert await _indicator_results(db_session) == []

    delete_again = await client.request(
        "DELETE", "/api/v1/idp/registros", json={"all": True}, headers=auth_header("ADMIN")
    )
    assert delete_again.json()["deleted"] == 0


async def test_delete_by_period_recalculates(client, auth_header, db_session) -> None:
    await _import_records(
        client, auth_header,
        [
            _idp_row(unit="Nova Mutum", rso_numero=34, month=6),
            _idp_row(unit="Rio Verde", rso_numero=1, month=7),
        ],
    )

    deleted = await client.request(
        "DELETE", "/api/v1/idp/registros",
        json={"periodStartYear": 2026, "periodStartMonth": 6, "periodEndYear": 2026, "periodEndMonth": 6},
        headers=auth_header("ADMIN"),
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 1

    remaining = (await db_session.execute(select(IdpRsoRecord))).scalars().all()
    assert len(remaining) == 1
    assert remaining[0].unit == "Rio Verde"

    # recalcIdpIndicators sempre recalcula a competência mais recente
    # disponível (sem período travado) -> só sobrou julho/2026.
    results = await _indicator_results(db_session)
    assert len(results) == 1
    assert results[0].month == 7


async def test_excluded_units_setting_via_configuracoes_recalculates(client, auth_header, db_session) -> None:
    await _import_records(client, auth_header, [_idp_row(unit="Nova Mutum")])
    before = (await _indicator_results(db_session))[0]
    assert before.value > 0

    patched = await client.patch(
        "/api/v1/configuracoes",
        json={"key": "idp.excludedUnits", "value": ["nova mutum", "nova mutum"]},
        headers=auth_header("ADMIN"),
    )
    assert patched.status_code == 200
    assert patched.json()["setting"]["value"] == ["MTU"]  # normalizado + dedup

    db_session.expire_all()
    after = (await _indicator_results(db_session))[0]
    assert after.value == 0  # única unidade agora excluída -> aderência geral None -> 0


async def test_excluded_disciplines_setting_accepts_multiline_string(client, auth_header) -> None:
    patched = await client.patch(
        "/api/v1/configuracoes",
        json={"key": "idp.excludedDisciplines", "value": "09 _ Projetos\n10 _ Fornecimentos"},
        headers=auth_header("ADMIN"),
    )
    assert patched.status_code == 200
    assert patched.json()["setting"]["value"] == ["09 _ Projetos", "10 _ Fornecimentos"]


async def test_publish_creates_version_and_deactivates_previous(client, auth_header) -> None:
    await _import_records(client, auth_header, [_idp_row()])

    publish_body = {
        "periodStartYear": 2026, "periodStartMonth": 6, "periodEndYear": 2026, "periodEndMonth": 6,
        "threshold": 90,
    }
    first = await client.post("/api/v1/publicacoes/idp", json=publish_body, headers=auth_header("ADMIN"))
    assert first.status_code == 200
    assert first.json()["publication"]["version"] == 1
    assert first.json()["publication"]["payload"]["unidades"][0]["rsoNumero"] == 34

    await _import_records(client, auth_header, [_idp_row(rso_numero=35, fase_real=53.08)], batch_number=2)

    second = await client.post("/api/v1/publicacoes/idp", json=publish_body, headers=auth_header("ADMIN"))
    assert second.status_code == 200
    assert second.json()["publication"]["version"] == 2

    history = await client.get(
        "/api/v1/publicacoes/idp"
        "?periodStartYear=2026&periodStartMonth=6&periodEndYear=2026&periodEndMonth=6",
        headers=auth_header("VIEWER"),
    )
    assert history.status_code == 200
    assert history.json()["publication"]["version"] == 2
    assert history.json()["historyCount"] >= 1


async def test_publish_without_rsos_in_period_is_domain_error(client, auth_header) -> None:
    response = await client.post(
        "/api/v1/publicacoes/idp",
        json={"periodStartYear": 2026, "periodStartMonth": 6, "periodEndYear": 2026, "periodEndMonth": 6},
        headers=auth_header("ADMIN"),
    )
    assert response.status_code == 422


async def test_publish_with_all_active_units_excluded_is_domain_error_not_500(client, auth_header) -> None:
    """Correção aplicada (decisions.md §4.2.5): no HEAD original, esse
    cenário caía num 500 genérico sem a mensagem de negócio."""
    await _import_records(client, auth_header, [_idp_row(unit="Nova Mutum")])
    await client.patch(
        "/api/v1/configuracoes", json={"key": "idp.excludedUnits", "value": ["MTU"]},
        headers=auth_header("ADMIN"),
    )

    response = await client.post(
        "/api/v1/publicacoes/idp",
        json={"periodStartYear": 2026, "periodStartMonth": 6, "periodEndYear": 2026, "periodEndMonth": 6},
        headers=auth_header("ADMIN"),
    )
    assert response.status_code == 422
    assert "execu" in response.json()["error"].lower()


async def test_viewer_cannot_publish(client, auth_header) -> None:
    await _import_records(client, auth_header, [_idp_row()])
    response = await client.post(
        "/api/v1/publicacoes/idp",
        json={"periodStartYear": 2026, "periodStartMonth": 6, "periodEndYear": 2026, "periodEndMonth": 6},
        headers=auth_header("VIEWER"),
    )
    assert response.status_code == 403


async def test_corrupted_persisted_row_does_not_crash_get_idp(client, auth_header, db_session) -> None:
    """Correção mandatória (decisions.md §4.2.4): um `IdpRsoRecord`
    corrompido no banco (ex.: `discData` com item faltando `prevAcum`) é
    ignorado, não derruba a rota inteira com 500."""
    await _import_records(client, auth_header, [_idp_row(unit="Nova Mutum", rso_numero=34)])

    db_session.add(
        IdpRsoRecord(
            businessKey="IDP_RSO:corrupted-row-key",
            contentHash="corrupted-hash",
            unit="Balsas", detectedUnit="Balsas", unitAdjusted=False,
            rsoNumero=1, detectedRsoNumero=1, rsoAdjusted=False,
            referenceYear=2026, referenceMonth=6, detectedReferenceYear=2026, detectedReferenceMonth=6,
            referenceSource="PDF_MES_REF", referenceOriginalText=None, referenceAdjusted=False,
            periodStart=None, periodEnd=None, emissionDate=None, fileName="corrompido.pdf",
            areas=["Pipe Rack"],
            discData={"01 - Civil": [{"area": "Pipe Rack"}]},  # faltam prevAcum/realAcum
            execucaoFases=[{"label": "Fase 1", "prevAcum": 50, "realAcum": 45}],
            raw={}, firstImportId="00000000-0000-0000-0000-000000000000",
            lastImportId="00000000-0000-0000-0000-000000000000",
        )
    )
    await db_session.commit()

    response = await client.get("/api/v1/idp", headers=auth_header("VIEWER"))
    assert response.status_code == 200
    assert response.json()["invalidRecordsSkipped"] == 1
    assert response.json()["total"] == 2  # conta os 2 registros persistidos, válido + corrompido
