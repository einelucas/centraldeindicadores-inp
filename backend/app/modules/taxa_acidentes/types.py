"""Tipos e constantes puros da Taxa de Acidentes.

Porte literal de `src/features/taxa-acidentes/types/index.ts`. Este módulo
não faz importação de planilha/HTML — todos os lançamentos (`AccidentMonthlyRecord`
e `AccidentUnitRecord`) são cadastrados manualmente via
`POST /taxa-acidentes` (ver `service.py`/`router.py`). Confirmado no
inventário: nenhuma das duas tabelas tem `businessKey`/`contentHash`/
`firstImportId`/`lastImportId`, e não há rota de upload/parse.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.shared.period import PeriodRange

# Meta padrão ("quanto menor a taxa, melhor" — atende quando resultado <= meta).
ACCIDENT_RATE_TARGET = 7.5

# Constantes fixas usadas no payload publicado (Scorecard/Painel Geral).
ACCIDENT_RATE_SCORECARD_WEIGHT = 0.2
ACCIDENT_RATE_SCORECARD_POINTS = 2_316.4

MODULE = "taxa-acidentes"
INDICATOR = "taxa"
GENERAL_PANEL_KEY = "taxa_acidentes"

ACCIDENT_TARGET_SETTING_KEY = "taxa-acidentes.target"
ACCIDENT_EXCLUDED_SETTING_KEY = "taxa-acidentes.excludedUnits"


@dataclass(frozen=True, slots=True)
class AccidentMonthlyInput:
    """Espelha `AccidentMonthlyRecord` (id opcional para uso em cálculo puro)."""

    year: int
    month: int
    rate: float
    caf: int
    id: str | None = None


@dataclass(frozen=True, slots=True)
class AccidentUnitInput:
    """Espelha `AccidentUnitRecord` já normalizado (`unit`/`unit_key`)."""

    year: int
    month: int
    unit: str
    unit_key: str
    saf: int
    caf: int
    id: str | None = None


@dataclass(frozen=True, slots=True)
class AccidentMonthlyResult:
    id: str | None
    year: int
    month: int
    rate: float
    caf: int
    label: str
    ok: bool


@dataclass(frozen=True, slots=True)
class AccidentUnitResult:
    id: str | None
    year: int
    month: int
    unit: str
    unit_key: str
    saf: int
    caf: int
    label: str
    excluded: bool


@dataclass(frozen=True, slots=True)
class AccidentRateResult:
    target: float
    excluded_units: list[str]
    period: PeriodRange | None
    result: float | None
    total_caf: int
    total_unit_caf: int
    total_saf: int
    latest_rate: float | None
    latest_year: int | None
    latest_month: int | None
    months_count: int
    monthly: list[AccidentMonthlyResult]
    units: list[AccidentUnitResult]
