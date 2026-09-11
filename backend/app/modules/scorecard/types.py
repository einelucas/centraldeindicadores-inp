"""Constantes e definição dos indicadores do Scorecard — alinhamento
2026-alinhamento-v2 (RDO 35% / Cronograma 40% / RNC 15% / Horas Extras 10%
reservado). A soma dos quatro pesos OFICIAIS é exatamente 100%; apenas os
três primeiros (90% de peso) participam do cálculo hoje — Horas Extras é um
indicador em desenvolvimento, sem fonte, sem fórmula e sem pontuação. O pool
mensal é 1/6 dos 11.582 pontos do ciclo
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
"""Pontuação máxima disponível em cada mês do ciclo (100% oficial)."""


@dataclass(frozen=True, slots=True)
class IndicatorSource:
    """Chave (`module`, `indicator`) de origem em `IndicatorPublication`."""

    module: str
    indicator: str


@dataclass(frozen=True, slots=True)
class ActiveScorecardIndicator:
    """Indicador que participa do cálculo: tem fonte, direção, unidade e
    meta avaliável. Único tipo aceito por `calculations.score_indicator` —
    passar um `DevelopmentScorecardIndicator` para lá é erro de tipo
    (mypy), não runtime."""

    key: str
    label: str
    area: str
    peso: float
    meta: float
    direction: Direction
    unit: str
    source: IndicatorSource
    status: Literal["active"] = "active"
    scoring_enabled: Literal[True] = True


@dataclass(frozen=True, slots=True)
class DevelopmentScorecardIndicator:
    """Indicador com peso oficial reservado, mas sem fórmula/fonte/pontuação
    definidas ainda. Nunca é avaliado, nunca gera pontos, nunca aceita
    resultado manual. `meta_reference` é só metadado de referência (ex.: o
    "1" de Horas Extras) até a regra de negócio ser definida — não é uma
    meta comparável."""

    key: str
    label: str
    area: str
    peso: float
    meta_reference: float | None
    status: Literal["development"] = "development"
    scoring_enabled: Literal[False] = False


ScorecardIndicator = ActiveScorecardIndicator | DevelopmentScorecardIndicator


SC_INDICATORS: tuple[ScorecardIndicator, ...] = (
    ActiveScorecardIndicator(
        key="rdo",
        label="Aprovação RDO",
        area="Obras",
        peso=35,
        meta=80,
        direction="higher",
        unit="%",
        source=IndicatorSource(module="rdo", indicator="aprovacao"),
    ),
    ActiveScorecardIndicator(
        key="cronograma",
        label="Aderência Cronograma",
        area="Planejamento",
        peso=40,
        meta=90,
        direction="higher",
        unit="%",
        source=IndicatorSource(module="idp", indicator="aderencia"),
    ),
    ActiveScorecardIndicator(
        key="rnc",
        label="RNC",
        area="Conformidade de Obra",
        peso=15,
        meta=15,
        direction="lower",
        unit="dias",
        source=IndicatorSource(module="rnc", indicator="dias_tratativa"),
    ),
    DevelopmentScorecardIndicator(
        key="horas_extras",
        label="Horas Extras Pagas",
        area="RH",
        peso=10,
        meta_reference=1,
    ),
)

SC_INDICATORS_BY_KEY: dict[str, ScorecardIndicator] = {
    indicator.key: indicator for indicator in SC_INDICATORS
}

SC_ACTIVE_INDICATORS: tuple[ActiveScorecardIndicator, ...] = tuple(
    indicator for indicator in SC_INDICATORS if isinstance(indicator, ActiveScorecardIndicator)
)

SCORECARD_OFFICIAL_WEIGHT_TOTAL: float = sum(indicator.peso for indicator in SC_INDICATORS)
"""Soma dos pesos dos quatro indicadores oficiais — sempre 100."""

SCORECARD_ACTIVE_WEIGHT_TOTAL: float = sum(indicator.peso for indicator in SC_ACTIVE_INDICATORS)
"""Soma dos pesos só dos indicadores que pontuam hoje — 90 enquanto Horas
Extras estiver em desenvolvimento. Quando Horas Extras virar ativo, este
valor passa a 100 automaticamente, sem redistribuir os outros pesos."""

SCORECARD_RESERVED_WEIGHT_TOTAL: float = SCORECARD_OFFICIAL_WEIGHT_TOTAL - SCORECARD_ACTIVE_WEIGHT_TOTAL
"""Peso oficial reservado para indicadores em desenvolvimento — 10."""

SCORECARD_ACTIVE_COVERAGE_PCT: float = (
    (SCORECARD_ACTIVE_WEIGHT_TOTAL / SCORECARD_OFFICIAL_WEIGHT_TOTAL) * 100
    if SCORECARD_OFFICIAL_WEIGHT_TOTAL
    else 0.0
)
"""Cobertura ativa do Scorecard nesta fase — 90.0 (%)."""

SHORT_LABELS: dict[str, str] = {
    "rdo": "RDO",
    "cronograma": "Cronograma",
    "rnc": "RNC",
    "horas_extras": "Horas Extras",
}

SCORECARD_PANEL_PERIOD_SETTING = "scorecard.panelPeriod"
"""Chave única em `AppSetting` — período de controle do Scorecard/Painel Geral."""

SCORECARD_POLICY_ID = "2026-alinhamento-v2"
"""Identificação de política gravada em novos `ScorecardSnapshot.raw` —
permite distinguir snapshots gerados sob o alinhamento vigente dos
anteriores (que não têm este campo)."""

SUPPORTED_PANEL_MODULES: frozenset[str] = frozenset({"rdo", "idp", "rnc"})
"""Módulos de origem considerados no `historyCount` do Painel Geral —
apenas os indicadores ativos do Scorecard têm módulo de origem."""
