"""Schemas Pydantic do módulo 5S — payloads em camelCase (paridade com o
Next.js atual). Porte de `src/features/cinco-s/schemas/index.ts` (entrada) e
das formas de resposta observadas em `src/app/api/cinco-s/**` /
`src/app/api/publicacoes/cinco-s/**`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import Field, model_validator

from app.shared.schema import CamelModel

_ExcludedUnit = Annotated[str, Field(max_length=100)]


# --- Entrada de registros (revalidação server-side de um lote de importação) ---


class FiveSAreaIn(CamelModel):
    divisao: str | None = None
    area: str = Field(min_length=1)
    meta: float
    nota: float


class FiveSRecordIn(CamelModel):
    unit: str = Field(min_length=1)
    year: int
    month: int = Field(ge=1, le=12)
    areas: list[FiveSAreaIn] = Field(min_length=1)
    raw: dict[str, Any]


# --- Saída de cálculo (GET /cinco-s) ---


class FiveSAreaOut(CamelModel):
    divisao: str | None
    area: str
    meta: float
    nota: float


class FiveSUnitMonthOut(CamelModel):
    unit: str
    year: int
    month: int
    aderencia: float
    excluded: bool
    areas: list[FiveSAreaOut]


class FiveSMonthResultOut(CamelModel):
    year: int
    month: int
    label: str
    geral: float | None
    units_count: int


class PeriodRangeOut(CamelModel):
    start_year: int
    start_month: int
    end_year: int
    end_month: int


class FiveSResultOut(CamelModel):
    threshold: float
    excluded_units: list[str]
    period: PeriodRangeOut | None
    period_label: str
    latest_year: int | None
    latest_month: int | None
    geral: float | None
    passa_meta: bool
    unit_months: list[FiveSUnitMonthOut]
    months: list[FiveSMonthResultOut]
    units_count: int
    months_count: int


class LastImportOut(CamelModel):
    id: str
    file_name: str
    completed_at: datetime | None
    total_found: int
    total_inserted: int
    total_updated: int
    total_ignored: int
    total_rejected: int


class FiveSGetOut(CamelModel):
    total: int
    threshold: float
    excluded_units: list[str]
    result: FiveSResultOut
    last_import: LastImportOut | None


# --- Configurações (PATCH /cinco-s) ---


class SettingsPatchIn(CamelModel):
    target: float = Field(ge=0, le=100)
    excluded_units: list[_ExcludedUnit] = Field(max_length=100)


class SettingsPatchOut(CamelModel):
    ok: bool = True
    threshold: float
    excluded_units: list[str]


# --- Registros (GET/DELETE /cinco-s/registros) ---


class RegistrosCountOut(CamelModel):
    count: int


class DeleteRegistrosIn(CamelModel):
    all_records: bool | None = Field(default=None, alias="all")
    period_start_year: int | None = Field(default=None, ge=2000, le=2200)
    period_start_month: int | None = Field(default=None, ge=1, le=12)
    period_end_year: int | None = Field(default=None, ge=2000, le=2200)
    period_end_month: int | None = Field(default=None, ge=1, le=12)

    @model_validator(mode="after")
    def _check_union(self) -> DeleteRegistrosIn:
        if self.all_records is True:
            return self
        has_full_period = (
            self.period_start_year is not None
            and self.period_start_month is not None
            and self.period_end_year is not None
            and self.period_end_month is not None
        )
        if has_full_period:
            return self
        raise ValueError('Informe {"all": true} ou os 4 campos de período.')


class DeleteRegistrosOut(CamelModel):
    ok: bool = True
    deleted: int


# --- Publicações (GET/POST /publicacoes/cinco-s) ---


class PublishedByOut(CamelModel):
    id: str
    name: str
    email: str


class PublicationOut(CamelModel):
    id: str
    version: int
    target: float | None
    result: float | None
    status: str | None
    payload: dict[str, Any]
    active: bool
    published_at: datetime
    cycle_year: int | None
    cycle_semester: str | None
    period_start_year: int | None
    period_start_month: int | None
    period_end_year: int | None
    period_end_month: int | None
    published_by: PublishedByOut


class PublicationGetOut(CamelModel):
    publication: PublicationOut | None
    history_count: int


class PublishIn(CamelModel):
    target: float = Field(default=95, ge=0, le=100)
    excluded_units: list[_ExcludedUnit] = Field(default_factory=lambda: ["SP", "CSC"], max_length=100)
    period_start_year: int | None = Field(default=None, ge=2000, le=2200)
    period_start_month: int | None = Field(default=None, ge=1, le=12)
    period_end_year: int | None = Field(default=None, ge=2000, le=2200)
    period_end_month: int | None = Field(default=None, ge=1, le=12)


class PublishOut(CamelModel):
    publication: PublicationOut
