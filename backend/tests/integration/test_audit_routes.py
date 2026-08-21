"""Testes de integração HTTP de `/auditoria`, contra Postgres real."""

from __future__ import annotations


async def test_audit_requires_admin(client, auth_header) -> None:
    forbidden = await client.get("/api/v1/auditoria", headers=auth_header("ANALYST"))
    assert forbidden.status_code == 403


async def test_audit_lists_entries_produced_by_other_routes(client, auth_header) -> None:
    await client.patch(
        "/api/v1/configuracoes",
        json={"key": "rnc.maxPrazoDias", "value": 20},
        headers=auth_header("ADMIN"),
    )

    response = await client.get("/api/v1/auditoria", headers=auth_header("ADMIN"))
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] >= 1
    actions = {item["action"] for item in body["items"]}
    assert "settings.update" in actions


async def test_audit_pagination_page_size_capped(client, auth_header) -> None:
    response = await client.get(
        "/api/v1/auditoria?pageSize=1000", headers=auth_header("ADMIN")
    )
    assert response.status_code == 200
    assert response.json()["pagination"]["pageSize"] <= 100
