"""Schemas Pydantic (camelCase) das rotas do Scorecard 2026."""

from __future__ import annotations

from pydantic import Field

from app.shared.schema import CamelModel


class PeriodRangeOut(CamelModel):
    start_year: int
    start_month: int
    end_year: int
    end_month: int


class ScorecardRowOut(CamelModel):
    key: str
    label: str
    peso: float
    meta: float
    direction: str
    unit: str
    value: float | None
    passed: bool = Field(alias="pass")
    pontos: float
    pontos_possiveis: float
    has_value: bool


class ScorecardResultOut(CamelModel):
    rows: list[ScorecardRowOut]
    total_pontos: float
    total_peso: float
    pontos_possiveis_mes: float
    atendimento_mes: float


class ScorecardComputationOut(CamelModel):
    year: int
    month: int
    source_values: dict[str, float | None]
    values: dict[str, float | None]
    result: ScorecardResultOut


class ScorecardSaveIn(CamelModel):
    year: int
    month: int = Field(ge=1, le=12)
    overrides: dict[str, float | None] = Field(default_factory=dict)


class ScorecardHistoryItemOut(CamelModel):
    year: int
    month: int
    values: dict[str, float | None]
    result: ScorecardResultOut


class ScorecardHistoryOut(CamelModel):
    snapshots: list[ScorecardHistoryItemOut]


class ScorecardHistoryDeleteOut(CamelModel):
    ok: bool
    deleted: int


class ScorecardPanelPeriodOut(CamelModel):
    period: PeriodRangeOut | None


class ScorecardPanelPeriodIn(CamelModel):
    start_year: int = Field(ge=2000, le=2200)
    start_month: int = Field(ge=1, le=12)
    end_year: int = Field(ge=2000, le=2200)
    end_month: int = Field(ge=1, le=12)
