"""Schemas Pydantic da rota de auditoria. Porte de `src/app/api/auditoria/route.ts`."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.shared.schema import CamelModel


class AuditLogUserOut(CamelModel):
    name: str
    email: str


class AuditLogOut(CamelModel):
    id: str
    user_id: str | None
    action: str
    entity: str
    entity_id: str | None
    previous_data: Any | None
    new_data: Any | None
    metadata: Any | None
    created_at: datetime
    user: AuditLogUserOut | None


class AuditPaginationOut(CamelModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class AuditListOut(CamelModel):
    items: list[AuditLogOut]
    pagination: AuditPaginationOut
