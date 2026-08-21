"""Constantes e estruturas de valor compartilhadas do módulo RDO.

Porte de `src/features/rdo/types/index.ts`. Nomes de status, metas e chaves
de configuração idênticos ao TypeScript original.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.shared.period import PeriodRange

# --- Constantes -------------------------------------------------------------

RDO_MODULE = "rdo"
RDO_INDICATOR = "aprovacao"
RDO_UNIT_ALL = "__ALL__"

RDO_DEFAULT_TARGET = 0.8
"""Meta fixa usada em `recalc_rdo_indicators` — NUNCA herda o threshold de
tela (GET /rdo) nem o threshold de publicação (POST /publicacoes/rdo). Ver
Divergência #2 do inventário: três noções de "meta" coexistem de propósito."""

RDO_PUBLISH_DEFAULT_THRESHOLD = 76.0
"""Default do campo `threshold` de POST /publicacoes/rdo — propositalmente
diferente de `RDO_DEFAULT_TARGET` (0.8 == 80%)."""

RDO_SCORECARD_POINTS = 2895.5
RDO_SCORECARD_WEIGHT = 0.25

RDO_EXCLUDED_UNITS_SETTING_KEY = "rdo.excludedUnits"

STATUS_APROVADO = "Aprovado"
STATUS_REVISAR = "Revisar Relatório"
STATUS_PREENCHENDO = "Preenchendo Relatório"

VALID_STATUS: tuple[str, str, str] = (STATUS_APROVADO, STATUS_REVISAR, STATUS_PREENCHENDO)


# --- Estruturas de valor ------------------------------------------------------


@dataclass(slots=True)
class RdoNormalizedRecord:
    """Registro normalizado usado como entrada de `compute_rdo_result`.

    `month` aqui é 1-based (campo persistido na tabela). Diferente de
    `RdoMonthAggregate.month`, que é 0-based (`Date.getMonth()`) — a mesma
    inconsistência documentada no TypeScript original (Divergência #11)."""

    data_referencia: datetime | None
    empresa_nome: str
    status_descricao: str
    relatorio_id: str | None
    grupo: str | None
    disciplina: str | None
    year: int
    month: int
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RdoUnitAggregate:
    name: str
    emitidos: int
    aprovados: int
    aderencia: float
    excluded: bool


@dataclass(slots=True)
class RdoMonthAggregate:
    year: int
    month: int  # 0-based (Date.getMonth()) — ver Divergência #11
    label: str
    emitidos: int
    aprovados: int
    aderencia: float


@dataclass(slots=True)
class RdoResult:
    threshold: float
    excluded_units: list[str]
    period: PeriodRange | None
    total_emitidos: int
    total_aprovados: int
    total_revisar: int
    total_preenchendo: int
    units: list[RdoUnitAggregate]
    unit_avg: float
    months: list[RdoMonthAggregate]
