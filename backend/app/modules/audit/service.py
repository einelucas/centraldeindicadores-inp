"""Serviço de auditoria. Porte de `src/app/api/auditoria/route.ts`."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.user import User


async def list_audit_logs(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    entity: str | None = None,
    action: str | None = None,
) -> tuple[list[AuditLog], int, dict[str, User]]:
    filters = []
    if entity:
        filters.append(AuditLog.entity == entity)
    if action:
        filters.append(AuditLog.action == action)

    stmt = select(AuditLog).order_by(AuditLog.createdAt.desc())
    count_stmt = select(func.count()).select_from(AuditLog)
    for condition in filters:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await session.execute(stmt)
    logs = list(result.scalars().all())
    total = (await session.execute(count_stmt)).scalar_one()

    user_ids = {log.userId for log in logs if log.userId is not None}
    users: dict[str, User] = {}
    if user_ids:
        users_result = await session.execute(select(User).where(User.id.in_(user_ids)))
        users = {u.id: u for u in users_result.scalars().all()}

    return logs, total, users
