"""Schemas Pydantic do módulo RNC — toda entrada/saída HTTP.

JSON sempre em camelCase (mesmo formato do Next.js atual, ver `CamelModel`);
nomes de campo em Python em snake_case.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import Field, StringConstraints, model_validator

from app.shared.schema import CamelModel

_ExcludedUnit = Annotated[str, StringConstraints(max_length=100)]
_NonEmptyId = Annotated[str, StringConstraints(min_length=1)]


# --- Importação (revalidação server-side, "Zod duas vezes") ------------------


class RncRecordIn(CamelModel):
    """Porte de `rncRecordSchema` — revalidado linha a linha dentro de
    `to_incremental_records`; o cliente nunca envia `businessKey`/`contentHash`."""

    status_rnc: str = ""
    unidade: str = ""
    data_criacao: str = Field(min_length=1)
    data_solucao: str | None = None
    tempo_tratativa: float | None = None
    ofensor: str = "N/A"
    year: int
    month: int = Field(ge=1, le=12)
    raw: dict[str, Any]


# --- GET /rnc -------------------------------------------------------------------


class PeriodRangeOut(CamelModel):
    start_year: int
    start_month: int
    end_year: int
    end_month: int


class RncUnitAggregateOut(CamelModel):
    name: str
    criadas: int
    tratadas: int
    aderencia: float
    tempos_tratativa: list[float]
    dias_medios: float | None
    dias_medianos: float | None
    tratativas_com_tempo: int
    maior_tempo_tratativa: float | None
    principal_ofensor: str | None
    principal_ofensor_count: int
    excluded: bool


class RncMonthAggregateOut(CamelModel):
    year: int
    month: int  # 0-based
    label: str
    chamados: int
    solucionados: int
    dias_medios: float | None
    dentro_meta: bool | None


class RncOfensorAggregateOut(CamelModel):
    name: str
    count: int
    pct: float


class RncResultOut(CamelModel):
    meta_dias: float
    excluded_units: list[str]
    period: PeriodRangeOut | None
    total_criadas: int
    total_tratadas: int
    aderencia_total: float
    resultado_dias: float | None
    months: list[RncMonthAggregateOut]
    units: list[RncUnitAggregateOut]
    ofensores: list[RncOfensorAggregateOut]


class RncLastImportOut(CamelModel):
    id: str
    file_name: str
    completed_at: datetime | None
    total_found: int
    total_inserted: int
    total_updated: int
    total_ignored: int
    total_rejected: int


class RncGetOut(CamelModel):
    total: int
    meta_dias: float
    result: RncResultOut
    last_import: RncLastImportOut | None


# --- PATCH /rnc (configuração de unidades excluídas) -----------------------------


class RncPatchSettingsIn(CamelModel):
    excluded_units: list[_ExcludedUnit] = Field(max_length=100)


class RncPatchSettingsOut(CamelModel):
    ok: bool
    excluded_units: list[str]


# --- GET /rnc/registros (contagem) ------------------------------------------------


class RncRecordsCountOut(CamelModel):
    count: int


# --- PATCH /rnc/registros (edição manual) -----------------------------------------


class RncEditIn(CamelModel):
    """`status`/`tempo_tratativa` ausentes do JSON não são tocados; presentes
    (mesmo como `null` para `tempo_tratativa`) substituem o valor atual. A
    distinção "ausente vs. null" é feita via `model_fields_set` no router —
    NUNCA usar apenas `is None` aqui."""

    id: _NonEmptyId
    status: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None = None
    tempo_tratativa: float | None = Field(default=None, ge=0, le=100000)


class RncEditUpdatedOut(CamelModel):
    id: str
    status_rnc: str
    tempo_tratativa: float | None


class RncEditOut(CamelModel):
    ok: bool
    unchanged: bool | None = None
    updated: RncEditUpdatedOut | None = None


# --- DELETE /rnc/registros -----------------------------------------------------------


class RncDeleteIn(CamelModel):
    """União de 3 formatos mutuamente exclusivos, distinguidos pela forma do
    JSON (não por um campo discriminador): `ids`, `all` ou os 4 campos de
    período."""

    ids: list[_NonEmptyId] | None = None
    all: bool | None = None
    period_start_year: int | None = None
    period_start_month: int | None = None
    period_end_year: int | None = None
    period_end_month: int | None = None

    @model_validator(mode="after")
    def _validate_shape(self) -> RncDeleteIn:
        has_ids = self.ids is not None
        has_all = self.all is True
        period_fields = (
            self.period_start_year,
            self.period_start_month,
            self.period_end_year,
            self.period_end_month,
        )
        has_full_period = all(v is not None for v in period_fields)
        has_any_period = any(v is not None for v in period_fields)

        modes_present = sum([has_ids, has_all, has_full_period])
        if modes_present != 1 or (has_any_period and not has_full_period):
            raise ValueError(
                "Corpo inválido: informe exatamente um de 'ids' (1 a 500), "
                "'all: true' ou os 4 campos de período (todos obrigatórios juntos)."
            )
        if has_ids and not (1 <= len(self.ids or []) <= 500):
            raise ValueError("ids deve conter de 1 a 500 identificadores.")
        if has_full_period:
            bounds = (
                (self.period_start_year, 2000, 2200),
                (self.period_start_month, 1, 12),
                (self.period_end_year, 2000, 2200),
                (self.period_end_month, 1, 12),
            )
            for value, lo, hi in bounds:
                if value is None or not (lo <= value <= hi):
                    raise ValueError("Período fora do intervalo permitido.")
        return self

    @property
    def mode(self) -> str:
        if self.ids is not None:
            return "ids"
        if self.all is True:
            return "all"
        return "period"


class RncDeleteOut(CamelModel):
    ok: bool
    deleted: int


# --- Publicações -------------------------------------------------------------------


class RncPublishIn(CamelModel):
    meta_dias: float = Field(default=15.0, ge=0, le=100000)
    period_start_year: int | None = Field(default=None, ge=2000, le=2200)
    period_start_month: int | None = Field(default=None, ge=1, le=12)
    period_end_year: int | None = Field(default=None, ge=2000, le=2200)
    period_end_month: int | None = Field(default=None, ge=1, le=12)


class PublishedByOut(CamelModel):
    id: str
    name: str
    email: str


class RncPublicationDetailOut(CamelModel):
    id: str
    version: int
    target: float | None
    result: float | None
    status: str | None
    payload: dict[str, Any]
    published_at: datetime
    published_by: PublishedByOut


class RncPublicationOut(CamelModel):
    publication: RncPublicationDetailOut | None


class RncPublicationsGetOut(CamelModel):
    publication: RncPublicationDetailOut | None
    history_count: int
