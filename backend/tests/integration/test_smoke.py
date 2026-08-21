"""Smoke test da infraestrutura de testes (health, auth, permissões)."""

from __future__ import annotations


async def test_health_live(client) -> None:
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_ready(client) -> None:
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200


async def test_auth_me_requires_token(client) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_auth_me_dev_bypass(client, auth_header) -> None:
    response = await client.get("/api/v1/auth/me", headers=auth_header("ADMIN"))
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "ADMIN"
    assert "users:manage" in body["permissions"]


async def test_auth_me_viewer_has_limited_permissions(client, auth_header) -> None:
    response = await client.get("/api/v1/auth/me", headers=auth_header("VIEWER"))
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "VIEWER"
    assert "users:manage" not in body["permissions"]
