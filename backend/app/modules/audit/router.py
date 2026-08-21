"""Rota de auditoria — `/auditoria`. Porte de `src/app/api/auditoria/route.ts`."""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission
from app.modules.audit import service
from app.modules.audit.schemas import AuditListOut, AuditLogOut, AuditLogUserOut, AuditPaginationOut

router = APIRouter()

# Teto de pageSize hardcoded em 100 no TS original — deliberadamente NÃO
# reaproveita `app/shared/pagination.py` (cujo teto vem de `MAX_PAGE_SIZE`,
# 200 por padrão), pois o contrato desta rota específica é 100, fixo.
_MAX_PAGE_SIZE = 100


@router.get("/auditoria", response_model=AuditListOut)
async def list_auditoria(
    page: int = Query(default=1),
    page_size: int = Query(default=50, alias="pageSize"),
    entity: str | None = Query(default=None),
    action: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.AUDIT_READ)),
) -> AuditListOut:
    page = max(1, page)
    page_size = min(_MAX_PAGE_SIZE, max(1, page_size))

    logs, total, users = await service.list_audit_logs(
        session, page=page, page_size=page_size, entity=entity, action=action
    )

    items = [
        AuditLogOut(
            id=log.id,
            user_id=log.userId,
            action=log.action,
            entity=log.entity,
            entity_id=log.entityId,
            previous_data=log.previousData,
            new_data=log.newData,
            metadata=log.metadata_,
            created_at=log.createdAt,
            user=(
                AuditLogUserOut(name=users[log.userId].name, email=users[log.userId].email)
                if log.userId is not None and log.userId in users
                else None
            ),
        )
        for log in logs
    ]

    return AuditListOut(
        items=items,
        pagination=AuditPaginationOut(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if page_size else 0,
        ),
    )
