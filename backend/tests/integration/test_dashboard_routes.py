"""Testes de integração HTTP do Painel Geral, contra Postgres real."""

from __future__ import annotations

import pytest

from app.models.indicators import IndicatorPublication


async def _admin_user_id(client, auth_header) -> str:
    response = await client.get("/api/v1/auth/me", headers=auth_header("ADMIN"))
    return response.json()["id"]


async def _publish(db_session, *, module, indicator, payload, user_id, cycle_year=None, cycle_semester=None):
    publication = IndicatorPublication(
        module=module, indicator=indicator, version=1, target=None, result=None, status="OK",
        payload=payload, active=True, publishedById=user_id,
        cycleYear=cycle_year, cycleSemester=cycle_semester,
    )
    db_session.add(publication)
    await db_session.commit()
    return publication


async def test_dashboard_percentages_scale_with_available_months(client, auth_header, db_session) -> None:
    admin_id = await _admin_user_id(client, auth_header)

    # RDO cumpre a meta (>=80) em 2 dos 6 meses do ciclo S1 2027 (Dez/26-Mai/27).
    await _publish(
        db_session, module="rdo", indicator="aprovacao", user_id=admin_id,
        payload={
            "resultado": 90.0, "emitidos": 10,
            "mensal": [{"label": "Dez/2026", "v": 90.0}, {"label": "Jan/2027", "v": 90.0}],
        },
        cycle_year=2027, cycle_semester="S1",
    )

    response = await client.get(
        "/api/v1/dashboard"
        "?periodStartYear=2026&periodStartMonth=12&periodEndYear=2027&periodEndMonth=5",
        headers=auth_header("VIEWER"),
    )
    assert response.status_code == 200
    body = response.json()

    assert body["pontuacaoPrevistaSemestre"] == 11582
    # 2 meses com dado -> pool mensal * 2, não o semestre completo de 6 meses.
    assert body["pontuacaoPrevista"] == pytest.approx(2 * (11582 / 6), rel=1e-9)
    # RDO (peso 25%) passou nos 2 meses -> pontosRealizados = 2 * (11582/6) * 0.25.
    expected_pontos = 2 * (11582 / 6) * 0.25
    assert body["pontosRealizados"] == pytest.approx(expected_pontos, rel=1e-9)
    # percentualDadosDisponiveis é contra os 2 meses disponíveis (denominador menor).
    assert body["percentualDadosDisponiveis"] == pytest.approx(25.0, rel=1e-6)
    # percentualSemestreCompleto é sempre contra os 11.582 pontos cheios (denominador maior).
    assert body["percentualSemestreCompleto"] < body["percentualDadosDisponiveis"]


async def test_available_periods_derived_from_publications(client, auth_header, db_session) -> None:
    admin_id = await _admin_user_id(client, auth_header)
    await _publish(
        db_session, module="rnc", indicator="dias_tratativa", user_id=admin_id,
        payload={"resultado": 10.0, "meta": 15.0, "mensal": [{"label": "Ago/2027", "v": 10.0}]},
    )

    response = await client.get("/api/v1/available-periods", headers=auth_header("VIEWER"))
    assert response.status_code == 200
    periods = response.json()["periods"]
    assert any(p["periodKey"] == "2027.S2" for p in periods)
    matched = next(p for p in periods if p["periodKey"] == "2027.S2")
    assert matched["monthStart"] == 6
    assert matched["monthEnd"] == 11
    assert {"year": 2027, "month": 8} in matched["competencies"]
