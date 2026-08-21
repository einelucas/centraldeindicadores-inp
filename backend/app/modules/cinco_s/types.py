"""Tipos e constantes do módulo 5S. Porte literal de
`src/features/cinco-s/types/index.ts`.

Regras preservadas (comentário original):
  - Aderência de área = min(nota/meta, 1).
  - Aderência da unidade/mês = média simples das aderências de área.
  - GERAL do mês = média simples das unidades NÃO excluídas com dados no mês.
  - Resultado atual = GERAL do último mês realmente existente na base.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.shared.period import PeriodRange

# Meta oficial do 5S: 90%.
FIVE_S_DEFAULT_TARGET = 0.9

# Unidades excluídas por padrão (regra do HTML de referência).
FIVE_S_DEFAULT_EXCLUDED: tuple[str, ...] = ("SP", "CSC")

# Participação do 5S no ciclo de 11.582 pontos.
FIVES_SCORECARD_POINTS = 1_158.2
FIVES_SCORECARD_WEIGHT = 0.1

# Chaves de AppSetting usadas exclusivamente pelo caminho `/cinco-s`.
FIVES_TARGET_SETTING = "fiveS.target"
FIVES_EXCLUDED_SETTING = "fiveS.excludedUnits"

MODULE_NAME = "cinco-s"
INDICATOR_NAME = "aderencia"


@dataclass(frozen=True, slots=True)
class FiveSArea:
    """Área auditada dentro de uma unidade."""

    divisao: str | None
    area: str
    meta: float
    nota: float


@dataclass(frozen=True, slots=True)
class FiveSNormalizedRecord:
    """Registro 5S normalizado: uma unidade num mês, com suas áreas."""

    unit: str
    year: int
    month: int  # 1..12
    areas: list[FiveSArea]
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FiveSUnitMonth:
    """Aderência de uma unidade num mês."""

    unit: str
    year: int
    month: int
    aderencia: float  # média das aderências de área (0-1)
    excluded: bool
    areas: list[FiveSArea]


@dataclass(frozen=True, slots=True)
class FiveSMonthResult:
    """Consolidado real de um mês."""

    year: int
    month: int
    label: str
    geral: float | None
    units_count: int


@dataclass(frozen=True, slots=True)
class FiveSResult:
    """Resultado consolidado do 5S."""

    threshold: float
    excluded_units: list[str]
    period: PeriodRange | None
    period_label: str
    latest_year: int | None
    latest_month: int | None
    geral: float | None
    passa_meta: bool
    unit_months: list[FiveSUnitMonth]
    months: list[FiveSMonthResult]
    units_count: int
    months_count: int
