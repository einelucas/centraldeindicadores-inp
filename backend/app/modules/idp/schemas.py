"""Schemas Pydantic do módulo IDP/RSO — toda entrada/saída HTTP.

JSON sempre em camelCase (mesmo formato do Next.js atual, ver `CamelModel`);
nomes de campo em Python em snake_case.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from app.shared.schema import CamelModel

ReferenceSourceIn = Literal["PDF_MES_REF", "MANUAL"]


# --- Importação (revalidação server-side, "Zod duas vezes") ------------------


class IdpAreaEntryIn(CamelModel):
    area: str
    prev_acum: float
    real_acum: float


class IdpExecutionPhaseIn(CamelModel):
    label: str
    prev_acum: float
    real_acum: float


class IdpRecordIn(CamelModel):
    """Porte de `idpRecordSchema`. O IDP não tem parsing de PDF no FastAPI —
    o navegador continua extraindo os campos e envia este JSON já
    normalizado, revalidado aqui antes de gerar `businessKey`/`contentHash`
    no servidor."""

    unit: str = Field(min_length=1)
    detected_unit: str | None = None
    unit_adjusted: bool = False
    rso_numero: int = Field(gt=0)
    detected_rso_numero: int | None = None
    rso_adjusted: bool = False
    reference_year: int
    reference_month: int = Field(ge=1, le=12)
    detected_reference_year: int | None = None
    detected_reference_month: int | None = None
    reference_source: ReferenceSourceIn
    reference_original_text: str | None = None
    reference_adjusted: bool = False
    period_start: str | None = None
    period_end: str | None = None
    emission_date: str | None = None
    file_name: str = Field(min_length=1)
    areas: list[str] = Field(default_factory=list)
    disc_data: dict[str, list[IdpAreaEntryIn]] = Field(default_factory=dict)
    execucao_fases: list[IdpExecutionPhaseIn] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


# --- GET /idp -------------------------------------------------------------------


class PeriodRangeOut(CamelModel):
    start_year: int
    start_month: int
    end_year: int
    end_month: int


class IdpExecutionPhaseOut(CamelModel):
    label: str
    prev_acum: float
    real_acum: float


class IdpUnitRowOut(CamelModel):
    unit: str
    rso_numero: int
    reference_year: int
    reference_month: int
    reference_source: str
    reference_original_text: str | None
    reference_adjusted: bool
    period_start: datetime | None
    period_end: datetime | None
    emission_date: datetime | None
    file_name: str
    n_fases: int
    prev_acum: float
    real_acum: float
    aderencia: float | None
    excluded: bool
    phases: list[IdpExecutionPhaseOut]


class IdpDisciplineRowOut(CamelModel):
    disciplina: str
    prev_avg: float | None
    real_avg: float | None
    aderencia: float | None


class IdpMonthAggregateOut(CamelModel):
    year: int
    month: int  # 1-based
    label: str
    aderencia: float | None
    active_documents: int
    total_previsto_medio: float
    total_real_medio: float


class IdpResultOut(CamelModel):
    threshold: float
    excluded_disciplines: list[str]
    excluded_units: list[str]
    selected_year: int
    selected_month: int
    history_start_year: int
    history_month_start: int
    history_end_year: int
    history_month_end: int
    active_documents: int
    aderencia_geral: float | None
    total_previsto_medio: float
    total_real_medio: float
    unit_rows: list[IdpUnitRowOut]
    discipline_rows: list[IdpDisciplineRowOut]
    monthly: list[IdpMonthAggregateOut]


class IdpDocumentOut(CamelModel):
    id: str
    unit: str
    detected_unit: str | None
    unit_adjusted: bool
    rso_numero: int
    detected_rso_numero: int | None
    rso_adjusted: bool
    reference_year: int
    reference_month: int
    detected_reference_year: int | None
    detected_reference_month: int | None
    reference_source: str
    reference_original_text: str | None
    reference_adjusted: bool
    period_start: datetime | None
    period_end: datetime | None
    emission_date: datetime | None
    file_name: str
    areas: int  # contagem, não o array — paridade com o HEAD (Divergência #6)
    active: bool
    same_competence: bool
    created_at: datetime
    updated_at: datetime
    first_imported_by: str | None
    last_updated_by: str | None


class IdpLastImportOut(CamelModel):
    id: str
    file_name: str
    completed_at: datetime | None
    total_found: int
    total_inserted: int
    total_updated: int
    total_ignored: int
    total_rejected: int


class IdpGetOut(CamelModel):
    total: int
    active_total: int
    threshold: float
    years: list[int]
    selected_year: int
    selected_month: int
    history_start_year: int
    history_month_start: int
    history_end_year: int
    history_month_end: int
    excluded_disciplines: list[str]
    result: IdpResultOut
    documents: list[IdpDocumentOut]
    last_import: IdpLastImportOut | None
    invalid_records_skipped: int = 0
    """Quantidade de `IdpRsoRecord` persistidos que falharam a revalidação e
    foram excluídos do cálculo — em vez de derrubar a rota com 500 (correção
    mandatória do prompt de migração, ver decisions.md §4.2.4). `0` no caso
    comum (nenhum registro corrompido)."""


# --- GET/DELETE /idp/registros -------------------------------------------------------


class IdpRecordsCountOut(CamelModel):
    count: int


class IdpDeleteIn(CamelModel):
    """União de 2 formatos mutuamente exclusivos: `all` ou os 4 campos de
    período — o IDP NÃO tem exclusão por `ids` (diferente de RDO/RNC)."""

    all: bool | None = None
    period_start_year: int | None = None
    period_start_month: int | None = None
    period_end_year: int | None = None
    period_end_month: int | None = None

    @model_validator(mode="after")
    def _validate_shape(self) -> IdpDeleteIn:
        has_all = self.all is True
        period_fields = (
            self.period_start_year, self.period_start_month,
            self.period_end_year, self.period_end_month,
        )
        has_full_period = all(v is not None for v in period_fields)
        has_any_period = any(v is not None for v in period_fields)

        if sum([has_all, has_full_period]) != 1 or (has_any_period and not has_full_period):
            raise ValueError(
                "Corpo inválido: informe 'all: true' ou os 4 campos de período (todos obrigatórios juntos)."
            )
        if has_full_period:
            bounds = (
                (self.period_start_year, 2000, 2200), (self.period_start_month, 1, 12),
                (self.period_end_year, 2000, 2200), (self.period_end_month, 1, 12),
            )
            for value, lo, hi in bounds:
                if value is None or not (lo <= value <= hi):
                    raise ValueError("Período fora do intervalo permitido.")
        return self

    @property
    def mode(self) -> str:
        return "all" if self.all is True else "period"


class IdpDeleteOut(CamelModel):
    ok: bool
    deleted: int


# --- Publicações -------------------------------------------------------------------


class IdpPublishIn(CamelModel):
    period_start_year: int = Field(ge=2000, le=2200)
    period_start_month: int = Field(ge=1, le=12)
    period_end_year: int = Field(ge=2000, le=2200)
    period_end_month: int = Field(ge=1, le=12)
    threshold: float = Field(default=90.0, ge=0, le=200)


class PublishedByOut(CamelModel):
    id: str
    name: str
    email: str


class IdpPublicationDetailOut(CamelModel):
    id: str
    version: int
    target: float | None
    result: float | None
    status: str | None
    payload: dict[str, Any]
    published_at: datetime
    published_by: PublishedByOut


class IdpPublicationOut(CamelModel):
    publication: IdpPublicationDetailOut | None


class IdpPublicationsGetOut(CamelModel):
    publication: IdpPublicationDetailOut | None
    history_count: int
