"""AuditLog — trilha de auditoria."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import Timestamp3, utcnow, uuid_pk


class AuditLog(Base):
    __tablename__ = "AuditLog"

    id: Mapped[str] = uuid_pk()
    userId: Mapped[str | None] = mapped_column(
        String, ForeignKey("User.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True
    )
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity: Mapped[str] = mapped_column(String, nullable=False)
    entityId: Mapped[str | None] = mapped_column(String, nullable=True)
    previousData: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    newData: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)

    __table_args__ = (
        Index("AuditLog_entity_entityId_idx", "entity", "entityId"),
        Index("AuditLog_userId_idx", "userId"),
        Index("AuditLog_createdAt_idx", "createdAt"),
    )
