"""Constantes e estruturas de valor compartilhadas do módulo RNC.

Porte de `src/features/rnc/types/index.ts`. Nomes de status, metas e chaves
de configuração idênticos ao TypeScript original.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.shared.period import PeriodRange

# --- Constantes -------------------------------------------------------------

RNC_MODULE = "rnc"
RNC_INDICATOR = "dias_tratativa"
RNC_UNIT_ALL = "__ALL__"

RNC_DEFAULT_MAX_DIAS = 15.0
"""Meta fixa usada em `recalc_rnc_indicators` e como default de exibição/
publicação — `<=` conta como dentro da meta (menor é melhor)."""

RNC_STATUS_TRATADA = "TRATADA"
"""Critério usado para `tratadas`/`aderencia` por unidade e para
`totalTratadas`/`aderenciaTotal` — DIFERENTE do critério usado para
`solucionados` no agregado mensal (que é baseado em `dataSolucao` estar
preenchida, independente de `statusRnc`). Ver Divergência #4 do inventário:
as duas noções de "solucionada" convivem de propósito e NÃO devem ser
fundidas."""

RNC_SCORECARD_POINTS = 1158.2
RNC_SCORECARD_WEIGHT = 0.1

RNC_EXCLUDED_UNITS_SETTING_KEY = "rnc.excludedUnits"


# --- Estruturas de valor ------------------------------------------------------


@dataclass(slots=True)
class RncNormalizedRecord:
    """Registro normalizado usado como entrada de `compute_rnc_result`.

    `month`/`year` aqui são 1-based (campo persistido na tabela). O agregado
    mensal (`RncMonthAggregate.month`) é 0-based (`Date.getMonth()`) — mesma
    inconsistência documentada em RDO (Divergência #7 do inventário RNC)."""

    status_rnc: str
    unidade: str
    data_criacao: datetime | None
    data_solucao: datetime | None
    tempo_tratativa: float | None
    ofensor: str
    year: int
    month: int
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RncUnitAggregate:
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


@dataclass(slots=True)
class RncMonthAggregate:
    year: int
    month: int  # 0-based (Date.getMonth())
    label: str
    chamados: int
    solucionados: int
    dias_medios: float | None
    dentro_meta: bool | None


@dataclass(slots=True)
class RncOfensorAggregate:
    name: str
    count: int
    pct: float  # fração 0-1, não percentual


@dataclass(slots=True)
class RncResult:
    meta_dias: float
    excluded_units: list[str]
    period: PeriodRange | None
    total_criadas: int
    total_tratadas: int
    aderencia_total: float
    resultado_dias: float | None
    months: list[RncMonthAggregate]
    units: list[RncUnitAggregate]
    ofensores: list[RncOfensorAggregate]
