"""Testes de integração HTTP da Taxa de Acidentes, contra Postgres real."""

from __future__ import annotations


async def test_create_monthly_and_unit_entries(client, auth_header) -> None:
    monthly = await client.post(
        "/api/v1/taxa-acidentes",
        json={"type": "month", "year": 2027, "month": 3, "rate": 6.5, "caf": 2},
        headers=auth_header("ANALYST"),
    )
    assert monthly.status_code == 200
    assert monthly.json()["saved"]["rate"] == 6.5

    unit = await client.post(
        "/api/v1/taxa-acidentes",
        json={"type": "unit", "year": 2027, "month": 3, "unit": "LEM", "saf": 1, "caf": 0},
        headers=auth_header("ANALYST"),
    )
    assert unit.status_code == 200
    assert unit.json()["saved"]["unit"] == "LEM"

    forbidden = await client.post(
        "/api/v1/taxa-acidentes",
        json={"type": "month", "year": 2027, "month": 4, "rate": 1, "caf": 0},
        headers=auth_header("VIEWER"),
    )
    assert forbidden.status_code == 403


async def test_get_unfiltered_arrays_but_filtered_result(client, auth_header) -> None:
    await client.post(
        "/api/v1/taxa-acidentes",
        json={"type": "month", "year": 2027, "month": 1, "rate": 2.0, "caf": 0},
        headers=auth_header("ANALYST"),
    )
    await client.post(
        "/api/v1/taxa-acidentes",
        json={"type": "month", "year": 2027, "month": 8, "rate": 9.0, "caf": 1},
        headers=auth_header("ANALYST"),
    )

    response = await client.get(
        "/api/v1/taxa-acidentes"
        "?periodStartYear=2027&periodStartMonth=6&periodEndYear=2027&periodEndMonth=11",
        headers=auth_header("VIEWER"),
    )
    assert response.status_code == 200
    body = response.json()
    # monthly/units carregam TUDO, sem filtro de período (peculiaridade preservada).
    assert len(body["monthly"]) == 2
    # só o `result` aninhado respeita o período pedido.
    assert body["result"]["monthsCount"] == 1
    assert body["result"]["latestMonth"] == 8


async def test_delete_single_monthly_and_unit_entry(client, auth_header) -> None:
    await client.post(
        "/api/v1/taxa-acidentes",
        json={"type": "month", "year": 2027, "month": 5, "rate": 3.0, "caf": 0},
        headers=auth_header("ANALYST"),
    )
    unit_response = await client.post(
        "/api/v1/taxa-acidentes",
        json={"type": "unit", "year": 2027, "month": 5, "unit": "MTU", "saf": 0, "caf": 0},
        headers=auth_header("ANALYST"),
    )
    unit_id = unit_response.json()["saved"]["id"]

    delete_month = await client.request(
        "DELETE",
        "/api/v1/taxa-acidentes?kind=month&year=2027&month=5",
        headers=auth_header("ANALYST"),
    )
    assert delete_month.status_code == 200
    assert delete_month.json()["deleted"] == 1

    delete_unit = await client.request(
        "DELETE", f"/api/v1/taxa-acidentes?kind=unit&id={unit_id}", headers=auth_header("ANALYST")
    )
    assert delete_unit.status_code == 200
    assert delete_unit.json()["deleted"] == 1

    delete_unit_again = await client.request(
        "DELETE", f"/api/v1/taxa-acidentes?kind=unit&id={unit_id}", headers=auth_header("ANALYST")
    )
    assert delete_unit_again.status_code == 404


async def test_bulk_delete_requires_admin(client, auth_header) -> None:
    await client.post(
        "/api/v1/taxa-acidentes",
        json={"type": "month", "year": 2027, "month": 9, "rate": 4.0, "caf": 0},
        headers=auth_header("ANALYST"),
    )

    forbidden = await client.request(
        "DELETE", "/api/v1/taxa-acidentes/registros", json={"all": True}, headers=auth_header("ANALYST")
    )
    assert forbidden.status_code == 403

    ok = await client.request(
        "DELETE", "/api/v1/taxa-acidentes/registros", json={"all": True}, headers=auth_header("ADMIN")
    )
    assert ok.status_code == 200
    assert ok.json()["deleted"] == 1


async def test_publish_and_read_back(client, auth_header) -> None:
    await client.post(
        "/api/v1/taxa-acidentes",
        json={"type": "month", "year": 2027, "month": 3, "rate": 5.0, "caf": 1},
        headers=auth_header("ANALYST"),
    )

    published = await client.post(
        "/api/v1/publicacoes/taxa-acidentes", json={}, headers=auth_header("ADMIN")
    )
    assert published.status_code == 200
    assert published.json()["publication"]["version"] == 1
    assert published.json()["publication"]["payload"]["resultado"] == 5.0
    assert published.json()["publication"]["status"] == "OK"

    fetched = await client.get("/api/v1/publicacoes/taxa-acidentes", headers=auth_header("VIEWER"))
    assert fetched.status_code == 200
    assert fetched.json()["publication"]["version"] == 1


async def test_publish_without_records_is_domain_error(client, auth_header) -> None:
    response = await client.post(
        "/api/v1/publicacoes/taxa-acidentes", json={}, headers=auth_header("ADMIN")
    )
    assert response.status_code == 422
