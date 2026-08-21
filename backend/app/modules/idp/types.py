"""Constantes e estruturas de valor compartilhadas do módulo IDP/RSO.

Porte de `src/features/idp/types/index.ts`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

# --- Constantes -------------------------------------------------------------

IDP_MODULE = "idp"
IDP_INDICATOR = "aderencia"
IDP_UNIT_ALL = "__ALL__"

IDP_DEFAULT_TARGET = 0.9

IDP_SCORECARD_POINTS = 4053.7
IDP_SCORECARD_WEIGHT = 0.35

IDP_EXCLUDED_DISCIPLINES_SETTING_KEY = "idp.excludedDisciplines"
IDP_EXCLUDED_UNITS_SETTING_KEY = "idp.excludedUnits"

IDP_DEFAULT_EXCLUDED_DISCIPLINES: tuple[str, ...] = ("10 _ Fornecimentos", "09 _ Projetos")

IDP_DISC_NAMES: tuple[str, ...] = (
    "01 - Civil",
    "02 - Mecânica",
    "03 - Mecânica de Rotativos",
    "04 - Elétrica",
    "05 - Instrumentação",
    "06 - Automação",
    "07 - Isolamento",
    "08 - Válvulas Manuais",
)

ReferenceSource = Literal["PDF_MES_REF", "MANUAL"]


# --- Estruturas de valor ------------------------------------------------------


@dataclass(slots=True)
class IdpAreaEntry:
    area: str
    prev_acum: float
    real_acum: float


@dataclass(slots=True)
class IdpExecutionPhase:
    label: str
    prev_acum: float
    real_acum: float


@dataclass(slots=True)
class IdpNormalizedRecord:
    """`id`/`updated_at` só existem para registros já persistidos — usados
    como `source_id` de `IdpUnitRow` e como primeira tentativa do desempate
    de versionamento (`tie_breaker_time`), respectivamente. Um registro
    recém-chegado de uma importação (ainda não gravado) tem `id=None` e
    `updated_at=None`."""

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
    areas: list[str]
    disc_data: dict[str, list[IdpAreaEntry]]
    execucao_fases: list[IdpExecutionPhase]
    raw: dict[str, Any] = field(default_factory=dict)
    id: str | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class IdpUnitRow:
    source_id: str | None
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
    phases: list[IdpExecutionPhase]
    """Fases de execução do RSO vencedor (`label`/`prev_acum`/`real_acum` por
    fase) — usado pelo gerador de justificativa do IDP para apontar o maior
    desvio de fase (previsto vs. realizado)."""


@dataclass(slots=True)
class IdpDisciplineRow:
    disciplina: str
    prev_avg: float | None
    real_avg: float | None
    aderencia: float | None


@dataclass(slots=True)
class IdpMonthAggregate:
    year: int
    month: int  # 1-based (referenceMonth já é 1-based, diferente de RDO/RNC)
    label: str
    aderencia: float | None
    active_documents: int
    total_previsto_medio: float
    total_real_medio: float


@dataclass(slots=True)
class IdpResult:
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
    unit_rows: list[IdpUnitRow]
    discipline_rows: list[IdpDisciplineRow]
    monthly: list[IdpMonthAggregate]
