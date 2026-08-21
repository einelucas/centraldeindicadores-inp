"""Payload de publicação do RDO. Porte literal de `toRdoPublishedPayload`
(`src/features/rdo/publications/index.ts`).

Assimetria de arredondamento intencional e confirmada pelos testes originais:
`resultado` / `emRevisaoPct` / `preenchendoPct` / `mensal[].v` usam 2 casas
decimais (`round_percent`); `unidades[].v` usa 0 casas (inteiro). Ambos usam
arredondamento "half up" (como `Math.round` do JS: `.5` sempre para cima),
não o banker's rounding do `round()` nativo do Python.
"""

from __future__ import annotations

import math
import re
from typing import Any, cast

from app.core.errors import DomainError
from app.modules.rdo.types import RDO_SCORECARD_POINTS, RDO_SCORECARD_WEIGHT, RdoResult
from app.shared.period import PeriodRange

__all__ = ["round_percent", "to_rdo_published_payload"]

_INPASA_PREFIX_RE = re.compile(r"^INPASA\s*", re.IGNORECASE)


def _round_half_up(value: float, decimals: int = 0) -> float:
    factor = 10**decimals
    return math.floor(value * factor + 0.5) / factor


def round_percent(value: float) -> float:
    """`Math.round(v * 100) / 100` — 2 casas decimais."""
    return _round_half_up(value, 2)


def _period_to_dict(period: PeriodRange | None) -> dict[str, int] | None:
    if period is None:
        return None
    return {
        "startYear": period.start_year,
        "startMonth": period.start_month,
        "endYear": period.end_year,
        "endMonth": period.end_month,
    }


def to_rdo_published_payload(result: RdoResult, target_percent: float) -> dict[str, Any]:
    """Guarda redundante/defensiva (Divergência #14): a rota já checa
    `result.total_emitidos <= 0` antes de chamar esta função, com mensagem
    ligeiramente diferente ("...para publicar a aprovação.")."""
    if result.total_emitidos <= 0:
        raise DomainError("Não há RDO emitido no período para calcular a aprovação.")

    resultado = round_percent((result.total_aprovados / result.total_emitidos) * 100)
    em_revisao_pct = round_percent((result.total_revisar / result.total_emitidos) * 100)
    preenchendo_pct = round_percent((result.total_preenchendo / result.total_emitidos) * 100)

    unidades: list[dict[str, str | int]] = sorted(
        (
            {
                "n": _INPASA_PREFIX_RE.sub("", unit.name).strip(),
                "v": int(_round_half_up(unit.aderencia * 100)),
            }
            for unit in result.units
            if unit.emitidos > 0 and not unit.excluded
        ),
        key=lambda item: cast(int, item["v"]),
        reverse=True,
    )

    mensal = [
        {
            "label": month.label,
            "v": round_percent((month.aprovados / month.emitidos) * 100) if month.emitidos > 0 else None,
        }
        for month in result.months
    ]

    return {
        "pontos": RDO_SCORECARD_POINTS,
        "peso": RDO_SCORECARD_WEIGHT,
        "meta": target_percent,
        "resultado": resultado,
        "aprovados": result.total_aprovados,
        "emitidos": result.total_emitidos,
        "emRevisaoPct": em_revisao_pct,
        "preenchendoPct": preenchendo_pct,
        "periodo": _period_to_dict(result.period),
        "unidades": unidades,
        "mensal": mensal,
    }
