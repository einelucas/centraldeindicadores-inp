"""AppSetting — metas, listas de exclusão e período de controle do Scorecard."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import Timestamp3, utcnow


class AppSetting(Base):
    __tablename__ = "AppSetting"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    # Valor JSON heterogêneo de propósito (Prisma `Json`, não um objeto
    # necessariamente): metas são float (`rdo.target = 0.8`), listas de
    # exclusão são list[str] (`fiveS.excludedUnits`), etc.
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )
