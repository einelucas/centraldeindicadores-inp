"""Testes de integração HTTP de `/indicadores`, contra Postgres real."""

from __future__ import annotations

from app.models.indicators import IndicatorResult


async def test_list_indicadores_requires_read_permission(client, auth_header, db_session) -> None:
    db_session.add(
        IndicatorResult(
            module="rdo", indicator="aprovacao", unit="__ALL__", year=2027, month=3,
            value=0.9, target=0.8, adherence=0.9, status="OK", details={},
        )
    )
    await db_session.commit()

    response = await client.get("/api/v1/indicadores?year=2027", headers=auth_header("VIEWER"))
    assert response.status_code == 200
    items = response.json()["items"]
    assert any(item["module"] == "rdo" and item["year"] == 2027 for item in items)
