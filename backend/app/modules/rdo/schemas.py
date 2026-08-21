"""Schemas Pydantic do módulo RDO — toda entrada/saída HTTP.

JSON sempre em camelCase (mesmo formato do Next.js atual, ver `CamelModel`);
nomes de campo em Python em snake_case.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints, model_validator

from app.shared.schema import CamelModel

_ExcludedUnit = Annotated[str, StringConstraints(max_length=200)]
_NonEmptyId = Annotated[str, StringConstraints(min_length=1)]

RdoStatus = Literal["Aprovado", "Revisar Relatório", "Preenchendo Relatório"]


# --- Importação (revalidação server-side, "Zod duas vezes") ------------------


class RdoRecordIn(CamelModel):
    """Porte de `rdoRecordSchema` — revalidado linha a linha dentro de
    `to_incremental_records`; o cliente nunca envia `businessKey`/`contentHash`."""

    data_referencia: str = Field(min_length=1)
    empresa_nome: str = Field(min_length=1)
    status_descricao: str = ""
    relatorio_id: str | None = None
    grupo: str | None = None
    disciplina: str | None = None
    year: int
    month: int = Field(ge=1, le=12)
    raw: dict[str, Any]


# --- GET /rdo -------------------------------------------------------------------


class PeriodRangeOut(CamelModel):
    start_year: int
    start_month: int
    end_year: int
    end_month: int


class RdoUnitAggregateOut(CamelModel):
    name: str
    emitidos: int
    aprovados: int
    aderencia: float
    excluded: bool


class RdoMonthAggregateOut(CamelModel):
    year: int
    month: int  # 0-based — ver Divergência #11
    label: str
    emitidos: int
    aprovados: int
    aderencia: float


class RdoResultOut(CamelModel):
    threshold: float
    excluded_units: list[str]
    period: PeriodRangeOut | None
    total_emitidos: int
    total_aprovados: int
    total_revisar: int
    total_preenchendo: int
    units: list[RdoUnitAggregateOut]
    unit_avg: float
    months: list[RdoMonthAggregateOut]


class RdoDetalheItemOut(CamelModel):
    id: str
    data: datetime
    unidade: str
    grupo: str | None
    disciplina: str | None
    status: str
    relatorio_id: str | None
    edited_manually: bool


class RdoFiltrosOut(CamelModel):
    unidades: list[str]
    anos: list[int]
    status: list[str]


class RdoLastImportOut(CamelModel):
    id: str
    file_name: str
    completed_at: datetime | None
    total_found: int
    total_inserted: int
    total_updated: int
    total_ignored: int
    total_rejected: int


class RdoGetOut(CamelModel):
    total: int
    threshold: float
    result: RdoResultOut
    detalhe: list[RdoDetalheItemOut]
    detalhe_limitado: bool
    filtros: RdoFiltrosOut
    last_import: RdoLastImportOut | None


# --- PATCH /rdo (configuração de unidades excluídas) -----------------------------


class RdoPatchSettingsIn(CamelModel):
    excluded_units: list[_ExcludedUnit] = Field(max_length=200)


class RdoPatchSettingsOut(CamelModel):
    ok: bool
    excluded_units: list[str]


# --- GET /rdo/registros (contagem) ------------------------------------------------


class RdoRecordsCountOut(CamelModel):
    count: int


# --- PATCH /rdo/registros (edição manual de status) -------------------------------


class RdoEditIn(CamelModel):
    id: _NonEmptyId
    status: RdoStatus


class RdoEditUpdatedOut(CamelModel):
    id: str
    status_descricao: str


class RdoEditOut(CamelModel):
    ok: bool
    unchanged: bool | None = None
    updated: RdoEditUpdatedOut | None = None


# --- DELETE /rdo/registros -----------------------------------------------------------


class RdoDeleteIn(CamelModel):
    """União de 3 formatos mutuamente exclusivos, distinguidos pela forma do
    JSON (não por um campo discriminador): `ids`, `all` ou os 4 campos de período."""

    ids: list[_NonEmptyId] | None = None
    all: bool | None = None
    period_start_year: int | None = None
    period_start_month: int | None = None
    period_end_year: int | None = None
    period_end_month: int | None = None

    @model_validator(mode="after")
    def _validate_shape(self) -> RdoDeleteIn:
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


class RdoDeleteOut(CamelModel):
    ok: bool
    deleted: int


# --- Publicações -------------------------------------------------------------------


class RdoPublishIn(CamelModel):
    threshold: float = Field(default=76.0, ge=0, le=100)
    period_start_year: int | None = Field(default=None, ge=2000, le=2200)
    period_start_month: int | None = Field(default=None, ge=1, le=12)
    period_end_year: int | None = Field(default=None, ge=2000, le=2200)
    period_end_month: int | None = Field(default=None, ge=1, le=12)


class PublishedByOut(CamelModel):
    id: str
    name: str
    email: str


class RdoPublicationDetailOut(CamelModel):
    id: str
    version: int
    target: float | None
    result: float | None
    status: str | None
    payload: dict[str, Any]
    published_at: datetime
    published_by: PublishedByOut


class RdoPublicationOut(CamelModel):
    publication: RdoPublicationDetailOut | None


class RdoPublicationsGetOut(CamelModel):
    publication: RdoPublicationDetailOut | None
    history_count: int
