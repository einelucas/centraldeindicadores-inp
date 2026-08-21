"""ImportJob, ImportBatch, ImportError — rastreio das importações incrementais."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import Timestamp3, utcnow, uuid_pk


class ImportStatus(str, enum.Enum):
    PENDING = "PENDING"
    PARSING = "PARSING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


ImportStatusEnum = PGEnum(ImportStatus, name="ImportStatus", create_type=False)


class ImportJob(Base):
    __tablename__ = "ImportJob"

    id: Mapped[str] = uuid_pk()
    module: Mapped[str] = mapped_column(String, nullable=False)
    fileName: Mapped[str] = mapped_column(String, nullable=False)
    referenceYear: Mapped[int | None] = mapped_column(Integer, nullable=True)
    referenceMonth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[ImportStatus] = mapped_column(
        ImportStatusEnum, nullable=False, default=ImportStatus.PENDING
    )
    totalFound: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    totalInserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    totalIgnored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    totalUpdated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    totalRejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    startedAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    completedAt: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)
    userId: Mapped[str] = mapped_column(
        String, ForeignKey("User.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    errorMessage: Mapped[str | None] = mapped_column(String, nullable=True)

    batches: Mapped[list[ImportBatch]] = relationship(back_populates="job", cascade="all,delete")
    errors: Mapped[list[ImportError]] = relationship(back_populates="job", cascade="all,delete")

    __table_args__ = (
        Index(
            "ImportJob_module_referenceYear_referenceMonth_idx",
            "module", "referenceYear", "referenceMonth",
        ),
        Index("ImportJob_userId_idx", "userId"),
        Index("ImportJob_status_idx", "status"),
    )


class ImportBatch(Base):
    __tablename__ = "ImportBatch"

    id: Mapped[str] = uuid_pk()
    importJobId: Mapped[str] = mapped_column(
        String, ForeignKey("ImportJob.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    batchNumber: Mapped[int] = mapped_column(Integer, nullable=False)
    totalReceived: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    totalInserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    totalIgnored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    totalUpdated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    totalRejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processedAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)

    job: Mapped[ImportJob] = relationship(back_populates="batches")

    __table_args__ = (
        Index("ImportBatch_importJobId_batchNumber_key", "importJobId", "batchNumber", unique=True),
    )


class ImportError(Base):
    __tablename__ = "ImportError"

    id: Mapped[str] = uuid_pk()
    importJobId: Mapped[str] = mapped_column(
        String, ForeignKey("ImportJob.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    batchNumber: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rowNumber: Mapped[int | None] = mapped_column(Integer, nullable=True)
    field: Mapped[str | None] = mapped_column(String, nullable=True)
    message: Mapped[str] = mapped_column(String, nullable=False)
    rawData: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)

    job: Mapped[ImportJob] = relationship(back_populates="errors")

    __table_args__ = (Index("ImportError_importJobId_idx", "importJobId"),)
