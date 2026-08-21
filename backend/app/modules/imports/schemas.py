"""Schemas Pydantic das rotas genéricas de importação."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.shared.schema import CamelModel


class StartImportIn(CamelModel):
    module: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    reference_year: int | None = None
    reference_month: int | None = Field(default=None, ge=1, le=12)
    total_found: int = Field(ge=0)


class StartImportOut(CamelModel):
    import_job_id: str
    status: str


class BatchIn(CamelModel):
    batch_number: int = Field(ge=1)
    records: list[dict[str, Any]]


class BatchErrorOut(CamelModel):
    business_key: str
    message: str


class BatchOut(CamelModel):
    inserted: int
    ignored: int
    updated: int
    rejected: int
    errors: list[BatchErrorOut]
    already_processed: bool


class FinalizeTotalsOut(CamelModel):
    found: int
    inserted: int
    ignored: int
    updated: int
    rejected: int


class FinalizeOut(CamelModel):
    status: str
    totals: FinalizeTotalsOut


class ImportBatchOut(CamelModel):
    id: str
    batch_number: int
    total_received: int
    total_inserted: int
    total_ignored: int
    total_updated: int
    total_rejected: int
    processed_at: datetime


class ImportJobOut(CamelModel):
    id: str
    module: str
    file_name: str
    reference_year: int | None
    reference_month: int | None
    status: str
    total_found: int
    total_inserted: int
    total_ignored: int
    total_updated: int
    total_rejected: int
    started_at: datetime
    completed_at: datetime | None
    user_id: str
    batches: list[ImportBatchOut] = Field(default_factory=list)


class ImportErrorOut(CamelModel):
    id: str
    batch_number: int | None
    row_number: int | None
    field: str | None
    message: str
    raw_data: dict[str, Any] | None
    created_at: datetime


class ImportErrorsOut(CamelModel):
    items: list[ImportErrorOut]
