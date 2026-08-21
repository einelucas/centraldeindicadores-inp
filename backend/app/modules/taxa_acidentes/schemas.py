"""Schemas Pydantic (camelCase) das rotas da Taxa de Acidentes.

Porte literal dos schemas Zod de `src/app/api/taxa-acidentes/route.ts`,
`src/app/api/taxa-acidentes/registros/route.ts` e
`src/app/api/publicacoes/taxa-acidentes/route.ts`. Limites de ano
propositalmente DIVERGENTES entre schemas (2000–2100 no cadastro
mensal/unidade, 2000–2200 no filtro de período e na exclusão em massa) —
inconsistência literal do TypeScript original, preservada aqui.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from app.shared.schema import CamelModel

_ENTRY_YEAR_MIN, _ENTRY_YEAR_MAX = 2000, 2100
_PERIOD_YEAR_MIN, _PERIOD_YEAR_MAX = 2000, 2200


def _trim_optional_id(value: Any) -> Any:
    if value is None:
        return None
    trimmed = str(value).strip()
    if not trimmed:
        raise ValueError("id não pode ser vazio")
    return trimmed


# --- POST /taxa-acidentes — união discriminada por `type` -----------------------


class MonthlyEntryIn(CamelModel):
    """`type: "month"` — cria ou atualiza (upsert) um `AccidentMonthlyRecord`."""

    type: Literal["month"]
    id: str | None = Field(default=None)
    year: int = Field(ge=_ENTRY_YEAR_MIN, le=_ENTRY_YEAR_MAX)
    month: int = Field(ge=1, le=12)
    rate: float = Field(ge=0)
    caf: int = Field(ge=0)

    @model_validator(mode="before")
    @classmethod
    def _trim_id(cls, data: Any) -> Any:
        if isinstance(data, dict) and "id" in data:
            data = dict(data)
            data["id"] = _trim_optional_id(data["id"])
        return data


class UnitEntryIn(CamelModel):
    """`type: "unit"` — cria ou atualiza (upsert) um `AccidentUnitRecord`."""

    type: Literal["unit"]
    id: str | None = Field(default=None)
    year: int = Field(ge=_ENTRY_YEAR_MIN, le=_ENTRY_YEAR_MAX)
    month: int = Field(ge=1, le=12)
    unit: str = Field(min_length=1, max_length=120)
    saf: int = Field(ge=0)
    caf: int = Field(ge=0)

    @model_validator(mode="before")
    @classmethod
    def _trim_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "id" in data:
                data["id"] = _trim_optional_id(data["id"])
            if isinstance(data.get("unit"), str):
                data["unit"] = data["unit"].strip()
        return data


class SettingsEntryIn(CamelModel):
    """`type: "settings"` — grava a meta (`target`)."""

    type: Literal["settings"]
    target: float = Field(ge=0)


AccidentEntryIn = Annotated[
    MonthlyEntryIn | UnitEntryIn | SettingsEntryIn,
    Field(discriminator="type"),
]


# --- PATCH /taxa-acidentes — unidades ignoradas ---------------------------------


class ExcludedUnitsIn(CamelModel):
    excluded_units: list[str] = Field(max_length=100)

    @model_validator(mode="after")
    def _check_item_length(self) -> ExcludedUnitsIn:
        for value in self.excluded_units:
            if len(value) > 100:
                raise ValueError("Cada unidade da lista deve ter no máximo 100 caracteres.")
        return self


# --- DELETE /taxa-acidentes/registros — união `{all:true}` | período completo ---


class DeleteRegistrosIn(CamelModel):
    all: bool | None = None
    period_start_year: int | None = Field(default=None, ge=_PERIOD_YEAR_MIN, le=_PERIOD_YEAR_MAX)
    period_start_month: int | None = Field(default=None, ge=1, le=12)
    period_end_year: int | None = Field(default=None, ge=_PERIOD_YEAR_MIN, le=_PERIOD_YEAR_MAX)
    period_end_month: int | None = Field(default=None, ge=1, le=12)

    @model_validator(mode="after")
    def _check_shape(self) -> DeleteRegistrosIn:
        if self.all is True:
            return self
        period_fields = (
            self.period_start_year,
            self.period_start_month,
            self.period_end_year,
            self.period_end_month,
        )
        if all(field is not None for field in period_fields):
            return self
        raise ValueError(
            "Informe { all: true } ou o período completo "
            "(periodStartYear, periodStartMonth, periodEndYear, periodEndMonth)."
        )


# --- POST /publicacoes/taxa-acidentes -------------------------------------------


class PublishIn(CamelModel):
    period_start_year: int | None = Field(default=None, ge=_PERIOD_YEAR_MIN, le=_PERIOD_YEAR_MAX)
    period_start_month: int | None = Field(default=None, ge=1, le=12)
    period_end_year: int | None = Field(default=None, ge=_PERIOD_YEAR_MIN, le=_PERIOD_YEAR_MAX)
    period_end_month: int | None = Field(default=None, ge=1, le=12)


# --- Saídas ----------------------------------------------------------------------


class MonthlyRowOut(CamelModel):
    id: str
    year: int
    month: int
    rate: float
    caf: int


class UnitRowOut(CamelModel):
    id: str
    year: int
    month: int
    unit: str
    unit_key: str
    saf: int
    caf: int


class MonthlyResultOut(MonthlyRowOut):
    label: str
    ok: bool


class UnitResultOut(UnitRowOut):
    label: str
    excluded: bool


class PeriodRangeOut(CamelModel):
    start_year: int
    start_month: int
    end_year: int
    end_month: int


class AccidentRateResultOut(CamelModel):
    target: float
    excluded_units: list[str]
    period: PeriodRangeOut | None
    result: float | None
    total_caf: int
    total_unit_caf: int
    total_saf: int
    latest_rate: float | None
    latest_year: int | None
    latest_month: int | None
    months_count: int
    monthly: list[MonthlyResultOut]
    units: list[UnitResultOut]


class GetTaxaAcidentesOut(CamelModel):
    """Resposta de `GET /taxa-acidentes`.

    ⚠️ `monthly`/`units` aqui NÃO são filtrados por período — carregam todas
    as linhas das duas tabelas. Só `result` (aninhado) respeita o período
    pedido via query string. Peculiaridade preservada de propósito, ver
    `service.load_accident_rate_data`."""

    monthly: list[MonthlyRowOut]
    units: list[UnitRowOut]
    target: float
    excluded_units: list[str]
    result: AccidentRateResultOut


class ExcludedUnitsOut(CamelModel):
    ok: bool
    excluded_units: list[str]


class MonthlySavedOut(CamelModel):
    id: str
    year: int
    month: int
    rate: float
    caf: int


class UnitSavedOut(CamelModel):
    id: str
    year: int
    month: int
    unit: str
    unit_key: str
    saf: int
    caf: int


class SettingsSavedOut(CamelModel):
    target: float


class MonthlySavedEnvelope(CamelModel):
    saved: MonthlySavedOut


class UnitSavedEnvelope(CamelModel):
    saved: UnitSavedOut


class SettingsSavedEnvelope(CamelModel):
    saved: SettingsSavedOut


class DeleteResultOut(CamelModel):
    ok: bool
    deleted: int


class RegistrosCountOut(CamelModel):
    count: int


class PublishedByOut(CamelModel):
    id: str
    name: str
    email: str


class PublicationOut(CamelModel):
    id: str
    module: str
    indicator: str
    version: int
    target: float | None
    result: float | None
    status: str | None
    payload: dict[str, Any]
    active: bool
    published_by_id: str
    published_at: str
    cycle_year: int | None
    cycle_semester: str | None
    period_start_year: int | None
    period_start_month: int | None
    period_end_year: int | None
    period_end_month: int | None
    published_by: PublishedByOut


class GetPublicationOut(CamelModel):
    publication: PublicationOut | None
    history_count: int


class PublishOut(CamelModel):
    publication: PublicationOut
