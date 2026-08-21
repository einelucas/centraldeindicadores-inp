"""Schemas Pydantic (camelCase) do Painel Geral — `GET /dashboard`,
`GET /available-periods`."""

from __future__ import annotations

from datetime import datetime

from app.shared.schema import CamelModel


class PeriodRangeOut(CamelModel):
    start_year: int
    start_month: int
    end_year: int
    end_month: int


class CompetencyOut(CamelModel):
    year: int
    month: int


class AvailablePeriodOut(CamelModel):
    """Contrato não ambíguo de período operacional pedido pela migração —
    complementa (não substitui) o `PeriodRange` `startYear/startMonth/...`
    já usado nas demais rotas."""

    period_key: str
    reference_year: int
    semester: str
    month_start: int
    month_end: int
    competencies: list[CompetencyOut]
    label: str


class AvailablePeriodsOut(CamelModel):
    periods: list[AvailablePeriodOut]


class PublicationRefOut(CamelModel):
    id: str
    version: int
    published_at: datetime
    published_by_id: str
    published_by_name: str
    published_by_email: str


class GeneralPanelMonthCellOut(CamelModel):
    key: str
    label: str
    value: float | None
    passed: bool | None
    pct_of_meta: float | None


class GeneralPanelIndicatorOut(CamelModel):
    key: str
    label: str
    short_label: str
    peso: float
    meta: float
    direction: str
    unit: str
    result: float | None
    has_data: bool
    passed: bool | None
    partial: float | None
    partial_pass: bool | None
    months: list[GeneralPanelMonthCellOut]
    publication: PublicationRefOut | None


class GeneralPanelOut(CamelModel):
    has_data: bool
    period: PeriodRangeOut
    period_key: str
    month_keys: list[str]
    month_labels: list[str]
    pontuacao_prevista: float
    pontuacao_prevista_semestre: float
    pontos_realizados: float
    atendimento_geral: float
    percentual_semestre_completo: float
    percentual_dados_disponiveis: float
    reference_date: datetime | None
    indicators: list[GeneralPanelIndicatorOut]
