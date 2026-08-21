"""Testes de integração HTTP de `/configuracoes`, contra Postgres real."""

from __future__ import annotations


async def test_get_readable_by_viewer_patch_requires_settings_manage(client, auth_header) -> None:
    readable = await client.get("/api/v1/configuracoes", headers=auth_header("VIEWER"))
    assert readable.status_code == 200
    assert readable.json()["items"] == []

    forbidden = await client.patch(
        "/api/v1/configuracoes",
        json={"key": "rdo.target", "value": 0.85},
        headers=auth_header("ANALYST"),
    )
    assert forbidden.status_code == 403

    ok = await client.patch(
        "/api/v1/configuracoes",
        json={"key": "rdo.target", "value": 0.85},
        headers=auth_header("ADMIN"),
    )
    assert ok.status_code == 200
    assert ok.json()["setting"]["value"] == 0.85


async def test_patch_stores_raw_value_without_conversion(client, auth_header) -> None:
    response = await client.patch(
        "/api/v1/configuracoes",
        json={"key": "fiveS.excludedUnits", "value": ["sp", "csc"]},
        headers=auth_header("ADMIN"),
    )
    assert response.status_code == 200
    # Valor bruto persistido tal como enviado — sem normalização de unidade.
    assert response.json()["setting"]["value"] == ["sp", "csc"]

    listed = await client.get("/api/v1/configuracoes", headers=auth_header("VIEWER"))
    entry = next(item for item in listed.json()["items"] if item["key"] == "fiveS.excludedUnits")
    assert entry["value"] == ["sp", "csc"]
