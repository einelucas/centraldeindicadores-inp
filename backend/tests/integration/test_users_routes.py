"""Testes de integração HTTP de `/usuarios`, contra Postgres real."""

from __future__ import annotations

from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.user import User


async def _current_user_id(client, auth_header, role: str) -> str:
    response = await client.get("/api/v1/auth/me", headers=auth_header(role))
    return response.json()["id"]


async def test_only_admin_can_list_and_create_users(client, auth_header) -> None:
    forbidden = await client.get("/api/v1/usuarios", headers=auth_header("ANALYST"))
    assert forbidden.status_code == 403

    created = await client.post(
        "/api/v1/usuarios",
        json={"name": "Ana Souza", "email": "ana@example.com", "role": "ANALYST"},
        headers=auth_header("ADMIN"),
    )
    assert created.status_code == 201
    assert created.json()["user"]["role"] == "ANALYST"
    assert created.json()["user"]["active"] is True

    listed = await client.get("/api/v1/usuarios", headers=auth_header("ADMIN"))
    assert listed.status_code == 200
    emails = {u["email"] for u in listed.json()["items"]}
    assert "ana@example.com" in emails


async def test_create_user_duplicate_email_conflicts(client, auth_header) -> None:
    body = {"name": "Bruno", "email": "bruno@example.com", "role": "VIEWER"}
    first = await client.post("/api/v1/usuarios", json=body, headers=auth_header("ADMIN"))
    assert first.status_code == 201

    second = await client.post("/api/v1/usuarios", json=body, headers=auth_header("ADMIN"))
    assert second.status_code == 409


async def test_admin_cannot_demote_or_deactivate_self(client, auth_header, db_session) -> None:
    admin_id = await _current_user_id(client, auth_header, "ADMIN")

    demote = await client.patch(
        f"/api/v1/usuarios/{admin_id}", json={"role": "VIEWER"}, headers=auth_header("ADMIN")
    )
    assert demote.status_code == 400

    deactivate = await client.patch(
        f"/api/v1/usuarios/{admin_id}", json={"active": False}, headers=auth_header("ADMIN")
    )
    assert deactivate.status_code == 400


async def test_update_user_records_audit_trail(client, auth_header, db_session) -> None:
    created = await client.post(
        "/api/v1/usuarios",
        json={"name": "Carla", "email": "carla@example.com", "role": "VIEWER"},
        headers=auth_header("ADMIN"),
    )
    user_id = created.json()["user"]["id"]

    updated = await client.patch(
        f"/api/v1/usuarios/{user_id}", json={"role": "ANALYST"}, headers=auth_header("ADMIN")
    )
    assert updated.status_code == 200
    assert updated.json()["user"]["role"] == "ANALYST"

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.entity == "User", AuditLog.entityId == user_id)
    )
    logs = result.scalars().all()
    actions = {log.action for log in logs}
    assert "user.create" in actions
    assert "user.update" in actions

    result = await db_session.execute(select(User).where(User.id == user_id))
    assert result.scalar_one().role.value == "ANALYST"
