"""Auditoria de operações. Porte de `src/server/audit/index.ts`.

Nunca armazena senhas, tokens ou segredos.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

_SENSITIVE_KEYS = {"password", "passwordhash", "token", "secret", "senha"}


def _redact(value: Any) -> Any:
    if value is None or not isinstance(value, dict | list):
        return value
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return {
        key: ("[REDACTED]" if key.lower() in _SENSITIVE_KEYS else _redact(val))
        for key, val in value.items()
    }


async def record_audit(
    session: AsyncSession,
    *,
    action: str,
    entity: str,
    user_id: str | None = None,
    entity_id: str | None = None,
    previous_data: Any = None,
    new_data: Any = None,
    metadata: Any = None,
) -> None:
    session.add(
        AuditLog(
            userId=user_id,
            action=action,
            entity=entity,
            entityId=entity_id,
            previousData=_redact(previous_data),
            newData=_redact(new_data),
            metadata_=_redact(metadata),
        )
    )
    await session.flush()
