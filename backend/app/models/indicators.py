"""IndicatorResult, IndicatorPublication, IndicatorJustification."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import Timestamp3, utcnow, uuid_pk

if TYPE_CHECKING:
    from app.models.user import User


class IndicatorResult(Base):
    __tablename__ = "IndicatorResult"

    id: Mapped[str] = uuid_pk()
    module: Mapped[str] = mapped_column(String, nullable=False)
    indicator: Mapped[str] = mapped_column(String, nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False, default="__ALL__")
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    target: Mapped[float | None] = mapped_column(Float, nullable=True)
    adherence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    updatedAt: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        Index(
            "IndicatorResult_module_indicator_unit_year_month_key",
            "module", "indicator", "unit", "year", "month", unique=True,
        ),
        Index("IndicatorResult_module_year_month_idx", "module", "year", "month"),
    )


class IndicatorPublication(Base):
    __tablename__ = "IndicatorPublication"

    id: Mapped[str] = uuid_pk()
    module: Mapped[str] = mapped_column(String, nullable=False)
    indicator: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    target: Mapped[float | None] = mapped_column(Float, nullable=True)
    result: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    publishedById: Mapped[str] = mapped_column(
        String, ForeignKey("User.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    publishedAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)

    cycleYear: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cycleSemester: Mapped[str | None] = mapped_column(String, nullable=True)
    periodStartYear: Mapped[int | None] = mapped_column(Integer, nullable=True)
    periodStartMonth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    periodEndYear: Mapped[int | None] = mapped_column(Integer, nullable=True)
    periodEndMonth: Mapped[int | None] = mapped_column(Integer, nullable=True)

    publishedBy: Mapped[User] = relationship()

    __table_args__ = (
        Index(
            "IndicatorPublication_module_indicator_version_key",
            "module", "indicator", "version", unique=True,
        ),
        Index(
            "IndicatorPublication_module_indicator_active_publishedAt_idx",
            "module", "indicator", "active", "publishedAt",
        ),
        Index("IndicatorPublication_publishedById_idx", "publishedById"),
        Index(
            "IndicatorPublication_module_indicator_cycle_idx",
            "module", "indicator", "cycleYear", "cycleSemester",
        ),
        # No máximo uma publicação ATIVA por módulo+indicador+ciclo (índice
        # único parcial — `prisma/manual/007_indicator_publication_cycle.sql`).
        # NULL é distinto de qualquer outro NULL em índice único no Postgres,
        # então publicações sem ciclo (cycleYear IS NULL) nunca colidem entre si.
        Index(
            "IndicatorPublication_active_cycle_key",
            "module", "indicator", "cycleYear", "cycleSemester",
            unique=True,
            postgresql_where=text('"active" = true'),
        ),
        # As duas famílias de colunas (cycleYear/cycleSemester e
        # periodStart.../periodEnd...) nunca podem ficar inconsistentes entre
        # si — mesma regra de `cycleFromYearSemester` em app/shared/period.py.
        # Convenção vigente (pós `008_fix_publication_cycle_year_convention.sql`):
        # para S1 o "ano do período" é o ano de TÉRMINO (maio), não o de início.
        CheckConstraint(
            '"cycleYear" IS NULL OR '
            '(("cycleSemester" = \'S2\' AND "periodStartYear" = "cycleYear" AND "periodStartMonth" = 6 '
            'AND "periodEndYear" = "cycleYear" AND "periodEndMonth" = 11) '
            'OR ("cycleSemester" = \'S1\' AND "periodStartYear" = "cycleYear" - 1 '
            'AND "periodStartMonth" = 12 AND "periodEndYear" = "cycleYear" AND "periodEndMonth" = 5))',
            name="IndicatorPublication_cycle_consistency_check",
        ),
    )


class IndicatorJustification(Base):
    __tablename__ = "IndicatorJustification"

    id: Mapped[str] = uuid_pk()
    module: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    result: Mapped[float | None] = mapped_column(Float, nullable=True)
    target: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    suggestedText: Mapped[str | None] = mapped_column(String, nullable=True)
    text: Mapped[str] = mapped_column(String, nullable=False)
    sourceImportId: Mapped[str | None] = mapped_column(String, nullable=True)
    sourceImportedAt: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)
    createdById: Mapped[str] = mapped_column(
        String, ForeignKey("User.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    updatedById: Mapped[str] = mapped_column(
        String, ForeignKey("User.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        Index("IndicatorJustification_module_year_month_key", "module", "year", "month", unique=True),
        Index("IndicatorJustification_module_year_month_idx", "module", "year", "month"),
        Index("IndicatorJustification_createdById_idx", "createdById"),
        Index("IndicatorJustification_updatedById_idx", "updatedById"),
    )
