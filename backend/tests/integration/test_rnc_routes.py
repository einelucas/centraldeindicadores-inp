"""Testes de integração HTTP do módulo RNC, contra Postgres real."""

from __future__ import annotations

from sqlalchemy import select

from app.models.indicators import IndicatorResult
from app.models.records import RncRecord


async def _import_records(client, auth_header, records: list[dict], batch_number: int = 1) -> str:
    start = await client.post(
        "/api/v1/importacoes/iniciar",
        json={"module": "rnc", "fileName": "planilha.xlsx", "totalFound": len(records)},
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


def _rnc_row(
    *,
    status: str = "ABERTA",
    unidade: str = "UNIDADE A",
    day: int = 5,
    data_solucao: str | None = None,
    tempo_tratativa: float | None = None,
    ofensor: str = "Fornecedor",
    year: int = 2027,
    month: int = 3,
) -> dict:
    return {
        "statusRnc": status,
        "unidade": unidade,
        "dataCriacao": f"{year}-{month:02d}-{day:02d}T00:00:00",
        "dataSolucao": data_solucao,
        "tempoTratativa": tempo_tratativa,
        "ofensor": ofensor,
        "year": year,
        "month": month,
        "raw": {},
    }


async def _indicator_results(db_session) -> list[IndicatorResult]:
    result = await db_session.execute(select(IndicatorResult).where(IndicatorResult.module == "rnc"))
    return list(result.scalars().all())


async def test_import_then_get_rnc(client, auth_header) -> None:
    records = [
        _rnc_row(status="TRATADA", day=1, data_solucao="2027-03-10T00:00:00", tempo_tratativa=7),
        _rnc_row(status="TRATADA", day=2, data_solucao="2027-03-20T00:00:00", tempo_tratativa=21),
        _rnc_row(status="ABERTA", day=3),
    ]
    await _import_records(client, auth_header, records)

    response = await client.get(
        "/api/v1/rnc"
        "?periodStartYear=2027&periodStartMonth=3&periodEndYear=2027&periodEndMonth=3",
        headers=auth_header("VIEWER"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["metaDias"] == 15
    assert body["result"]["totalCriadas"] == 3
    assert body["result"]["totalTratadas"] == 2
    assert body["result"]["resultadoDias"] == 14  # (7+21)/2
    month = body["result"]["months"][0]
    assert month["chamados"] == 3
    assert month["solucionados"] == 2
    assert month["diasMedios"] == 14
    assert month["dentroMeta"] is True


async def test_meta_query_param_changes_dentro_meta(client, auth_header) -> None:
    await _import_records(
        client, auth_header,
        [_rnc_row(status="TRATADA", data_solucao="2027-03-10T00:00:00", tempo_tratativa=14)],
    )

    default_meta = await client.get("/api/v1/rnc", headers=auth_header("VIEWER"))
    assert default_meta.json()["metaDias"] == 15
    assert default_meta.json()["result"]["months"][0]["dentroMeta"] is True

    tighter_meta = await client.get("/api/v1/rnc?meta=10", headers=auth_header("VIEWER"))
    assert tighter_meta.json()["metaDias"] == 10
    assert tighter_meta.json()["result"]["months"][0]["dentroMeta"] is False


async def test_reimport_is_idempotent(client, auth_header, db_session) -> None:
    records = [_rnc_row(status="TRATADA", data_solucao="2027-03-10T00:00:00", tempo_tratativa=7)]
    await _import_records(client, auth_header, records)
    await _import_records(client, auth_header, records, batch_number=2)

    result = await db_session.execute(select(RncRecord))
    assert len(result.scalars().all()) == 1


async def test_dual_definitions_of_solved_can_diverge(client, auth_header) -> None:
    """`dataSolucao` preenchida com `statusRnc != "TRATADA"` conta como
    "solucionado" no mês, mas NÃO como "tratado" na unidade/total — as duas
    métricas propositalmente divergem (ver Divergência #4 do inventário)."""
    await _import_records(
        client, auth_header,
        [_rnc_row(status="REABERTA", data_solucao="2027-03-10T00:00:00", tempo_tratativa=5)],
    )

    response = await client.get("/api/v1/rnc", headers=auth_header("VIEWER"))
    body = response.json()["result"]
    assert body["months"][0]["solucionados"] == 1  # dataSolucao presente
    assert body["totalTratadas"] == 0  # statusRnc != "TRATADA"


async def test_patch_excluded_units_requires_import_run(client, auth_header) -> None:
    forbidden = await client.patch(
        "/api/v1/rnc", json={"excludedUnits": ["LEM"]}, headers=auth_header("VIEWER")
    )
    assert forbidden.status_code == 403

    ok = await client.patch(
        "/api/v1/rnc", json={"excludedUnits": ["lem", "lem"]}, headers=auth_header("ANALYST")
    )
    assert ok.status_code == 200
    assert ok.json()["excludedUnits"] == ["LEM"]


async def test_registros_count_requires_admin(client, auth_header) -> None:
    await _import_records(client, auth_header, [_rnc_row(day=1), _rnc_row(day=2)])

    forbidden = await client.get("/api/v1/rnc/registros", headers=auth_header("ANALYST"))
    assert forbidden.status_code == 403

    ok = await client.get("/api/v1/rnc/registros", headers=auth_header("ADMIN"))
    assert ok.status_code == 200
    assert ok.json()["count"] == 2


async def test_edit_registro_status_and_tempo_tratativa(client, auth_header, db_session) -> None:
    await _import_records(
        client, auth_header,
        [_rnc_row(status="ABERTA", data_solucao="2027-03-10T00:00:00", tempo_tratativa=20)],
    )
    record = (await db_session.execute(select(RncRecord))).scalars().one()

    forbidden = await client.patch(
        "/api/v1/rnc/registros",
        json={"id": record.id, "status": "TRATADA"},
        headers=auth_header("ANALYST"),
    )
    assert forbidden.status_code == 403

    ok = await client.patch(
        "/api/v1/rnc/registros",
        json={"id": record.id, "status": "TRATADA", "tempoTratativa": 12},
        headers=auth_header("ADMIN"),
    )
    assert ok.status_code == 200
    assert ok.json()["updated"]["statusRnc"] == "TRATADA"
    assert ok.json()["updated"]["tempoTratativa"] == 12

    # No-op edit (mesmos valores) -> unchanged, sem auditoria/sem tocar editedManually.
    noop = await client.patch(
        "/api/v1/rnc/registros",
        json={"id": record.id, "status": "TRATADA", "tempoTratativa": 12},
        headers=auth_header("ADMIN"),
    )
    assert noop.status_code == 200
    assert noop.json()["unchanged"] is True

    # tempoTratativa: null explícito limpa o valor (campo PRESENTE, valor None).
    cleared = await client.patch(
        "/api/v1/rnc/registros",
        json={"id": record.id, "tempoTratativa": None},
        headers=auth_header("ADMIN"),
    )
    assert cleared.status_code == 200
    assert cleared.json()["updated"]["tempoTratativa"] is None
    assert cleared.json()["updated"]["statusRnc"] == "TRATADA"  # não tocado (campo ausente)


async def test_delete_by_ids_does_not_recalculate_indicator_result(client, auth_header, db_session) -> None:
    await _import_records(
        client, auth_header,
        [_rnc_row(status="TRATADA", data_solucao="2027-03-10T00:00:00", tempo_tratativa=7)],
    )
    before = await _indicator_results(db_session)
    assert len(before) == 1  # finalizar importação já recalculou

    record = (await db_session.execute(select(RncRecord))).scalars().one()
    deleted = await client.request(
        "DELETE", "/api/v1/rnc/registros", json={"ids": [record.id]}, headers=auth_header("ADMIN")
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 1

    remaining_records = (await db_session.execute(select(RncRecord))).scalars().all()
    assert remaining_records == []

    # IndicatorResult NÃO foi apagado nem recalculado por exclusão via `ids`.
    stale = await _indicator_results(db_session)
    assert len(stale) == 1


async def test_delete_all_removes_indicator_results(client, auth_header, db_session) -> None:
    await _import_records(
        client, auth_header,
        [_rnc_row(status="TRATADA", data_solucao="2027-03-10T00:00:00", tempo_tratativa=7)],
    )

    delete_all = await client.request(
        "DELETE", "/api/v1/rnc/registros", json={"all": True}, headers=auth_header("ADMIN")
    )
    assert delete_all.status_code == 200
    assert delete_all.json()["deleted"] == 1

    remaining_results = await _indicator_results(db_session)
    assert remaining_results == []

    delete_again = await client.request(
        "DELETE", "/api/v1/rnc/registros", json={"all": True}, headers=auth_header("ADMIN")
    )
    assert delete_again.json()["deleted"] == 0


async def test_delete_by_period_recalculates(client, auth_header, db_session) -> None:
    """`compute_rnc_result` calcula cada mês de forma independente, então
    apagar o único registro de março não altera o valor recalculado de abril
    — não dá para provar que o recálculo RODOU só olhando se o mês vazio
    desapareceu (ele nunca desaparece, ver `test_delete_by_ids_...`). Prova
    real: editar abril manualmente via `PATCH /rnc/registros` (que NUNCA
    recalcula, Divergência #2) deixa o `IndicatorResult` de abril
    propositalmente desatualizado; se o `DELETE` por período de fato
    recalcular, esse valor tem que ser corrigido como efeito colateral."""
    await _import_records(
        client, auth_header,
        [
            _rnc_row(status="TRATADA", data_solucao="2027-03-10T00:00:00", tempo_tratativa=7, day=1),
            _rnc_row(status="TRATADA", data_solucao="2027-04-10T00:00:00", tempo_tratativa=9, day=1, month=4),
        ],
    )

    april_record = (
        await db_session.execute(select(RncRecord).where(RncRecord.month == 4))
    ).scalars().one()
    edit = await client.patch(
        "/api/v1/rnc/registros",
        json={"id": april_record.id, "tempoTratativa": 99},
        headers=auth_header("ADMIN"),
    )
    assert edit.status_code == 200

    stale = next(r for r in await _indicator_results(db_session) if r.month == 4)
    assert stale.value == 9  # PATCH /registros não recalcula — ainda desatualizado.

    deleted = await client.request(
        "DELETE",
        "/api/v1/rnc/registros",
        json={
            "periodStartYear": 2027, "periodStartMonth": 3,
            "periodEndYear": 2027, "periodEndMonth": 3,
        },
        headers=auth_header("ADMIN"),
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 1

    remaining_records = (await db_session.execute(select(RncRecord))).scalars().all()
    assert len(remaining_records) == 1

    # `db_session` já carregou a linha de abril no mapa de identidade (em
    # `stale`); sem `expire_all()`, uma nova query devolveria o mesmo objeto
    # Python em cache em vez de refletir o commit feito pela sessão da
    # requisição HTTP de DELETE.
    db_session.expire_all()
    refreshed = next(r for r in await _indicator_results(db_session) if r.month == 4)
    assert refreshed.value == 99  # recalculado a partir do valor editado.


async def test_publish_creates_version_and_deactivates_previous(client, auth_header) -> None:
    await _import_records(
        client, auth_header,
        [_rnc_row(status="TRATADA", data_solucao="2027-03-10T00:00:00", tempo_tratativa=7)],
    )

    cycle_body = {
        "metaDias": 15,
        "periodStartYear": 2026, "periodStartMonth": 12,
        "periodEndYear": 2027, "periodEndMonth": 5,
    }

    first = await client.post("/api/v1/publicacoes/rnc", json=cycle_body, headers=auth_header("ADMIN"))
    assert first.status_code == 200
    assert first.json()["publication"]["version"] == 1
    assert first.json()["publication"]["payload"]["resultado"] == 7

    await _import_records(
        client, auth_header,
        [_rnc_row(status="TRATADA", data_solucao="2027-03-15T00:00:00", tempo_tratativa=21, day=6)],
        batch_number=2,
    )

    second = await client.post("/api/v1/publicacoes/rnc", json=cycle_body, headers=auth_header("ADMIN"))
    assert second.status_code == 200
    assert second.json()["publication"]["version"] == 2

    get_response = await client.get(
        "/api/v1/publicacoes/rnc"
        "?periodStartYear=2026&periodStartMonth=12&periodEndYear=2027&periodEndMonth=5",
        headers=auth_header("VIEWER"),
    )
    assert get_response.status_code == 200
    assert get_response.json()["publication"]["version"] == 2
    assert get_response.json()["historyCount"] >= 1


async def test_publish_without_records_is_domain_error(client, auth_header) -> None:
    response = await client.post(
        "/api/v1/publicacoes/rnc", json={"metaDias": 15}, headers=auth_header("ADMIN")
    )
    assert response.status_code == 422


async def test_publish_without_solved_treatment_time_is_domain_error(client, auth_header) -> None:
    await _import_records(client, auth_header, [_rnc_row(status="ABERTA")])
    response = await client.post(
        "/api/v1/publicacoes/rnc", json={"metaDias": 15}, headers=auth_header("ADMIN")
    )
    assert response.status_code == 422


async def test_viewer_cannot_publish(client, auth_header) -> None:
    await _import_records(
        client, auth_header,
        [_rnc_row(status="TRATADA", data_solucao="2027-03-10T00:00:00", tempo_tratativa=7)],
    )
    response = await client.post(
        "/api/v1/publicacoes/rnc", json={"metaDias": 15}, headers=auth_header("VIEWER")
    )
    assert response.status_code == 403
