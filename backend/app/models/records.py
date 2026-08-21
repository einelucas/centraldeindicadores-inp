"""Tabelas de registros importados — uma por módulo.

Campos de rastreio incremental comuns: businessKey, contentHash,
firstImportId, lastImportId, firstSeenAt, lastSeenAt.

Índices e nomes replicam exatamente o que os scripts `prisma/manual/*.sql`
aplicaram no banco real (não apenas `prisma/schema.prisma`), incluindo
`IdpRsoRecord`, criada fora do baseline do Prisma Migrate.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import Timestamp3, utcnow, uuid_pk


class RdoRecord(Base):
    __tablename__ = "RdoRecord"

    id: Mapped[str] = uuid_pk()
    businessKey: Mapped[str] = mapped_column(String, nullable=False)
    contentHash: Mapped[str] = mapped_column(String, nullable=False)
    dataReferencia: Mapped[datetime] = mapped_column(Timestamp3, nullable=False)
    empresaNome: Mapped[str] = mapped_column(String, nullable=False)
    statusDescricao: Mapped[str] = mapped_column(String, nullable=False)
    relatorioId: Mapped[str | None] = mapped_column(String, nullable=True)
    grupo: Mapped[str | None] = mapped_column(String, nullable=True)
    disciplina: Mapped[str | None] = mapped_column(String, nullable=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False)
    editedManually: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    editedBy: Mapped[str | None] = mapped_column(String, nullable=True)
    editedAt: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)
    firstImportId: Mapped[str] = mapped_column(String, nullable=False)
    lastImportId: Mapped[str] = mapped_column(String, nullable=False)
    firstSeenAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    lastSeenAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        Index("RdoRecord_businessKey_key", "businessKey", unique=True),
        Index("RdoRecord_year_month_idx", "year", "month"),
        Index("RdoRecord_empresaNome_idx", "empresaNome"),
        Index("RdoRecord_statusDescricao_idx", "statusDescricao"),
    )


class IdpRecord(Base):
    """Legado — não usado por nenhum caminho de código atual (confirmado via
    inventário). Preservado apenas para compatibilidade de schema; sem router."""

    __tablename__ = "IdpRecord"

    id: Mapped[str] = uuid_pk()
    businessKey: Mapped[str] = mapped_column(String, nullable=False)
    contentHash: Mapped[str] = mapped_column(String, nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    disciplina: Mapped[str] = mapped_column(String, nullable=False)
    custoLinhaBase: Mapped[float] = mapped_column(Float, nullable=False)
    custoReal: Mapped[float] = mapped_column(Float, nullable=False)
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False)
    firstImportId: Mapped[str] = mapped_column(String, nullable=False)
    lastImportId: Mapped[str] = mapped_column(String, nullable=False)
    firstSeenAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    lastSeenAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        Index("IdpRecord_businessKey_key", "businessKey", unique=True),
        Index("IdpRecord_year_month_idx", "year", "month"),
        Index("IdpRecord_unit_idx", "unit"),
    )


class IdpRsoRecord(Base):
    """Criada por `prisma/manual/005_idp_rso_versions.sql` (supersede a versão
    mais antiga `005_idp_rso.sql`, que usava `referenceDate` em vez de
    `referenceYear`/`referenceMonth` — não é a estrutura vigente)."""

    __tablename__ = "IdpRsoRecord"

    id: Mapped[str] = uuid_pk()
    businessKey: Mapped[str] = mapped_column(String, nullable=False)
    contentHash: Mapped[str] = mapped_column(String, nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    detectedUnit: Mapped[str | None] = mapped_column(String, nullable=True)
    unitAdjusted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rsoNumero: Mapped[int] = mapped_column(Integer, nullable=False)
    detectedRsoNumero: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rsoAdjusted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    referenceYear: Mapped[int] = mapped_column(Integer, nullable=False)
    referenceMonth: Mapped[int] = mapped_column(Integer, nullable=False)
    detectedReferenceYear: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detectedReferenceMonth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    referenceSource: Mapped[str] = mapped_column(String, nullable=False)
    referenceOriginalText: Mapped[str | None] = mapped_column(String, nullable=True)
    referenceAdjusted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    periodStart: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)
    periodEnd: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)
    emissionDate: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)
    fileName: Mapped[str] = mapped_column(String, nullable=False)
    areas: Mapped[dict] = mapped_column(JSONB, nullable=False)
    discData: Mapped[dict] = mapped_column(JSONB, nullable=False)
    execucaoFases: Mapped[dict] = mapped_column(JSONB, nullable=False)
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False)
    firstImportId: Mapped[str] = mapped_column(String, nullable=False)
    lastImportId: Mapped[str] = mapped_column(String, nullable=False)
    firstSeenAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    lastSeenAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        Index("IdpRsoRecord_businessKey_key", "businessKey", unique=True),
        Index("IdpRsoRecord_referenceYear_referenceMonth_idx", "referenceYear", "referenceMonth"),
        Index("IdpRsoRecord_unit_rsoNumero_idx", "unit", "rsoNumero"),
    )


class RncRecord(Base):
    __tablename__ = "RncRecord"

    id: Mapped[str] = uuid_pk()
    businessKey: Mapped[str] = mapped_column(String, nullable=False)
    contentHash: Mapped[str] = mapped_column(String, nullable=False)
    statusRnc: Mapped[str] = mapped_column(String, nullable=False)
    unidade: Mapped[str] = mapped_column(String, nullable=False)
    dataCriacao: Mapped[datetime] = mapped_column(Timestamp3, nullable=False)
    dataSolucao: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)
    tempoTratativa: Mapped[float | None] = mapped_column(Float, nullable=True)
    ofensor: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False)
    editedManually: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    editedBy: Mapped[str | None] = mapped_column(String, nullable=True)
    editedAt: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)
    firstImportId: Mapped[str] = mapped_column(String, nullable=False)
    lastImportId: Mapped[str] = mapped_column(String, nullable=False)
    firstSeenAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    lastSeenAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        Index("RncRecord_businessKey_key", "businessKey", unique=True),
        Index("RncRecord_year_month_idx", "year", "month"),
        Index("RncRecord_unidade_idx", "unidade"),
    )


class FiveSRecord(Base):
    __tablename__ = "FiveSRecord"

    id: Mapped[str] = uuid_pk()
    businessKey: Mapped[str] = mapped_column(String, nullable=False)
    contentHash: Mapped[str] = mapped_column(String, nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    aderencia: Mapped[float] = mapped_column(Float, nullable=False)
    areasCount: Mapped[int] = mapped_column(Integer, nullable=False)
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False)
    firstImportId: Mapped[str] = mapped_column(String, nullable=False)
    lastImportId: Mapped[str] = mapped_column(String, nullable=False)
    firstSeenAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    lastSeenAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        Index("FiveSRecord_businessKey_key", "businessKey", unique=True),
        Index("FiveSRecord_year_month_idx", "year", "month"),
        Index("FiveSRecord_unit_idx", "unit"),
    )


class AccidentMonthlyRecord(Base):
    __tablename__ = "AccidentMonthlyRecord"

    id: Mapped[str] = uuid_pk()
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    caf: Mapped[int] = mapped_column(Integer, nullable=False)
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        Index("AccidentMonthlyRecord_year_month_key", "year", "month", unique=True),
        Index("AccidentMonthlyRecord_year_month_idx", "year", "month"),
    )


class AccidentUnitRecord(Base):
    __tablename__ = "AccidentUnitRecord"

    id: Mapped[str] = uuid_pk()
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    unitKey: Mapped[str] = mapped_column(String, nullable=False)
    saf: Mapped[int] = mapped_column(Integer, nullable=False)
    caf: Mapped[int] = mapped_column(Integer, nullable=False)
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        Index("AccidentUnitRecord_year_month_unitKey_key", "year", "month", "unitKey", unique=True),
        Index("AccidentUnitRecord_year_month_idx", "year", "month"),
        Index("AccidentUnitRecord_unit_idx", "unit"),
    )


class ScorecardSnapshot(Base):
    __tablename__ = "ScorecardSnapshot"

    id: Mapped[str] = uuid_pk()
    businessKey: Mapped[str] = mapped_column(String, nullable=False)
    contentHash: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False)
    firstImportId: Mapped[str] = mapped_column(String, nullable=False)
    lastImportId: Mapped[str] = mapped_column(String, nullable=False)
    firstSeenAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    lastSeenAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        Index("ScorecardSnapshot_businessKey_key", "businessKey", unique=True),
        Index("ScorecardSnapshot_year_month_idx", "year", "month"),
    )
