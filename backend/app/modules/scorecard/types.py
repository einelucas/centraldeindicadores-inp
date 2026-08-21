"""Constantes e definição dos indicadores do Scorecard 2026.

Porte literal de `src/features/scorecard/types/index.ts`. A soma dos cinco
pesos é exatamente 100%; o pool mensal é 1/6 dos 11.582 pontos do ciclo
(`SCORECARD_MONTHLY_POOL = 11_582 / 6 = 1930.333...`). NÃO reimplementar
estes valores em outro lugar — sempre importar deste módulo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Direction = Literal["higher", "lower"]

SCORECARD_MAX_POINTS: int = 11_582
"""Pontuação máxima do ciclo de seis meses."""

SCORECARD_PERIOD_LENGTH: int = 6
"""Quantidade de meses de um ciclo padrão."""

SCORECARD_MONTHLY_POOL: float = SCORECARD_MAX_POINTS / SCORECARD_PERIOD_LENGTH
"""Pontuação máxima disponível em cada mês do ciclo."""


@dataclass(frozen=True, slots=True)
class IndicatorSource:
    """Chave (`module`, `indicator`) de origem em `IndicatorPublication`."""

    module: str
    indicator: str


@dataclass(frozen=True, slots=True)
class ScorecardIndicator:
    key: str
    label: str
    peso: float
    meta: float
    direction: Direction
    unit: str
    source: IndicatorSource | None


SC_INDICATORS: tuple[ScorecardIndicator, ...] = (
    ScorecardIndicator(
        key="rdo",
        label="Aprovação RDO",
        peso=25,
        meta=80,
        direction="higher",
        unit="%",
        source=IndicatorSource(module="rdo", indicator="aprovacao"),
    ),
    ScorecardIndicator(
        key="cronograma",
        label="Aderência Cronograma",
        peso=35,
        meta=90,
        direction="higher",
        unit="%",
        source=IndicatorSource(module="idp", indicator="aderencia"),
    ),
    ScorecardIndicator(
        key="rnc",
        label="RNC",
        peso=10,
        meta=15,
        direction="lower",
        unit="dias",
        source=IndicatorSource(module="rnc", indicator="dias_tratativa"),
    ),
    ScorecardIndicator(
        key="5s",
        label="5S",
        peso=10,
        meta=90,
        direction="higher",
        unit="%",
        source=IndicatorSource(module="cinco-s", indicator="aderencia"),
    ),
    ScorecardIndicator(
        key="taxa_acidentes",
        label="Taxa de Acidentes",
        peso=20,
        meta=7.5,
        direction="lower",
        unit="",
        source=IndicatorSource(module="taxa-acidentes", indicator="taxa"),
    ),
)

SC_INDICATORS_BY_KEY: dict[str, ScorecardIndicator] = {
    indicator.key: indicator for indicator in SC_INDICATORS
}

SHORT_LABELS: dict[str, str] = {
    "rdo": "RDO",
    "cronograma": "Cronograma",
    "rnc": "RNC",
    "5s": "5S",
    "taxa_acidentes": "Acidentes",
}

SCORECARD_PANEL_PERIOD_SETTING = "scorecard.panelPeriod"
"""Chave única em `AppSetting` — período de controle do Scorecard/Painel Geral."""

SUPPORTED_PANEL_MODULES: frozenset[str] = frozenset(
    {"rdo", "idp", "rnc", "cinco-s", "taxa-acidentes"}
)
"""Módulos de origem considerados no `historyCount` do Painel Geral."""
