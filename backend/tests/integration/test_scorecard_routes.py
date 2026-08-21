"""Testes de integração HTTP do Scorecard, contra Postgres real.

Publica `IndicatorPublication` diretamente via `db_session` (sem depender do
código Python dos módulos rdo/idp/rnc/cinco_s/taxa_acidentes, que vivem em
pacotes separados) — usa exatamente os formatos de payload que
`app/modules/scorecard/calculations.py::adapt_publication` espera por chave.
"""

from __future__ import annotations

from app.models.indicators import IndicatorPublication


async def _admin_user_id(client, auth_header) -> str:
    response = await client.get("/api/v1/auth/me", headers=auth_header("ADMIN"))
    return response.json()["id"]


def _rdo_payload(mensal: list[dict]) -> dict:
    return {"resultado": mensal[-1]["v"] if mensal else None, "emitidos": 10, "mensal": mensal}


async def _publish(
    db_session, *, module: str, indicator: str, version: int, active: bool, payload: dict, user_id: str
) -> IndicatorPublication:
    publication = IndicatorPublication(
        module=module, indicator=indicator, version=version, target=None, result=None,
        status="OK", payload=payload, active=active, publishedById=user_id,
    )
    db_session.add(publication)
    await db_session.commit()
    return publication


async def test_get_scorecard_with_no_data_returns_all_none(client, auth_header) -> None:
    response = await client.get("/api/v1/scorecard?year=2027&month=3", headers=auth_header("VIEWER"))
    assert response.status_code == 200
    body = response.json()
    assert all(v is None for v in body["values"].values())
    assert body["result"]["totalPontos"] == 0


async def test_get_scorecard_reads_live_published_value(client, auth_header, db_session) -> None:
    admin_id = await _admin_user_id(client, auth_header)
    await _publish(
        db_session, module="rdo", indicator="aprovacao", version=1, active=True,
        payload=_rdo_payload([{"label": "Mar/2027", "v": 85.0}]), user_id=admin_id,
    )

    response = await client.get("/api/v1/scorecard?year=2027&month=3", headers=auth_header("VIEWER"))
    assert response.status_code == 200
    body = response.json()
    assert body["sourceValues"]["rdo"] == 85.0
    assert body["values"]["rdo"] == 85.0
    row = next(r for r in body["result"]["rows"] if r["key"] == "rdo")
    assert row["pass"] is True


async def test_save_snapshot_then_live_still_wins_over_saved(client, auth_header, db_session) -> None:
    admin_id = await _admin_user_id(client, auth_header)
    await _publish(
        db_session, module="rdo", indicator="aprovacao", version=1, active=True,
        payload=_rdo_payload([{"label": "Mar/2027", "v": 70.0}]), user_id=admin_id,
    )

    saved = await client.post(
        "/api/v1/scorecard", json={"year": 2027, "month": 3}, headers=auth_header("ADMIN")
    )
    assert saved.status_code == 200
    assert saved.json()["values"]["rdo"] == 70.0

    # Republica com um valor NOVO — o vivo deve continuar vencendo o snapshot salvo antes.
    await _publish(
        db_session, module="rdo", indicator="aprovacao", version=2, active=True,
        payload=_rdo_payload([{"label": "Mar/2027", "v": 95.0}]), user_id=admin_id,
    )
    updated = await client.get("/api/v1/scorecard?year=2027&month=3", headers=auth_header("VIEWER"))
    assert updated.json()["values"]["rdo"] == 95.0


async def test_recovers_month_from_older_publication_version(client, auth_header, db_session) -> None:
    admin_id = await _admin_user_id(client, auth_header)
    # v1 (ativa depois desativada) cobre Jan; v2 (ativa) só cobre Fev.
    await _publish(
        db_session, module="rdo", indicator="aprovacao", version=1, active=False,
        payload=_rdo_payload([{"label": "Jan/2027", "v": 60.0}]), user_id=admin_id,
    )
    await _publish(
        db_session, module="rdo", indicator="aprovacao", version=2, active=True,
        payload=_rdo_payload([{"label": "Fev/2027", "v": 88.0}]), user_id=admin_id,
    )

    jan = await client.get("/api/v1/scorecard?year=2027&month=1", headers=auth_header("VIEWER"))
    assert jan.json()["values"]["rdo"] == 60.0

    fev = await client.get("/api/v1/scorecard?year=2027&month=2", headers=auth_header("VIEWER"))
    assert fev.json()["values"]["rdo"] == 88.0


async def test_history_requires_admin_and_explicit_period_for_delete(client, auth_header) -> None:
    forbidden = await client.request(
        "DELETE",
        "/api/v1/scorecard/history?periodStartYear=2026&periodStartMonth=12&periodEndYear=2027&periodEndMonth=5",
        headers=auth_header("ANALYST"),
    )
    assert forbidden.status_code == 403

    no_period = await client.request(
        "DELETE", "/api/v1/scorecard/history", headers=auth_header("ADMIN")
    )
    assert no_period.status_code == 422


async def test_history_lists_saved_snapshots_in_period(client, auth_header) -> None:
    await client.post("/api/v1/scorecard", json={"year": 2027, "month": 3}, headers=auth_header("ADMIN"))

    response = await client.get(
        "/api/v1/scorecard/history"
        "?periodStartYear=2026&periodStartMonth=12&periodEndYear=2027&periodEndMonth=5",
        headers=auth_header("VIEWER"),
    )
    assert response.status_code == 200
    assert any(s["year"] == 2027 and s["month"] == 3 for s in response.json()["snapshots"])


async def test_panel_period_get_and_patch(client, auth_header) -> None:
    empty = await client.get("/api/v1/scorecard/panel-period", headers=auth_header("VIEWER"))
    assert empty.json()["period"] is None

    saved = await client.patch(
        "/api/v1/scorecard/panel-period",
        json={"startYear": 2026, "startMonth": 12, "endYear": 2027, "endMonth": 5},
        headers=auth_header("ADMIN"),
    )
    assert saved.status_code == 200
    assert saved.json()["period"]["startMonth"] == 12

    fetched = await client.get("/api/v1/scorecard/panel-period", headers=auth_header("VIEWER"))
    assert fetched.json()["period"]["endMonth"] == 5
