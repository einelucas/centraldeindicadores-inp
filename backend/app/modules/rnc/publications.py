"""Payload de publicação do RNC. Porte literal de `toRncPublishedPayload`
(`src/features/rnc/publications/index.ts`).

Arredondamento propositalmente assimétrico e confirmado pelos testes
originais: `resultado` NÃO é arredondado (valor bruto da média mensal
simples); `mensal[].v` usa 2 casas decimais; `unidades[].v` e `ofensores[].pct`
usam, respectivamente, 0 e 1 casa decimal. Todos usam arredondamento
"half up" (como `Math.round` do JS), não o banker's rounding do Python.
"""

from __future__ import annotations

import math
import re
from typing import Any, cast

from app.core.errors import DomainError
from app.modules.rnc.types import RNC_SCORECARD_POINTS, RNC_SCORECARD_WEIGHT, RncResult
from app.shared.period import PeriodRange

__all__ = ["to_rnc_published_payload"]

_INPASA_PREFIX_RE = re.compile(r"^INPASA\s*", re.IGNORECASE)
_TOP_OFENSORES = 4
_OUTROS_THRESHOLD = 0.001


def _round_half_up(value: float, decimals: int = 0) -> float:
    factor = 10**decimals
    return math.floor(value * factor + 0.5) / factor


def _period_to_dict(period: PeriodRange | None) -> dict[str, int] | None:
    if period is None:
        return None
    return {
        "startYear": period.start_year,
        "startMonth": period.start_month,
        "endYear": period.end_year,
        "endMonth": period.end_month,
    }


def to_rnc_published_payload(result: RncResult) -> dict[str, Any]:
    """Guarda redundante/defensiva: a rota já checa `result.resultado_dias is
    None` antes de chamar esta função, com mensagem ligeiramente diferente
    ("...com Tempo de Tratativa numérico para publicar.")."""
    if result.resultado_dias is None:
        raise DomainError("Não há RNC solucionada com tempo de tratativa para publicar.")

    top = result.ofensores[:_TOP_OFENSORES]
    top_pct_sum = sum(o.pct for o in top)
    outros_pct = 1 - top_pct_sum

    unidades: list[dict[str, str | int]] = sorted(
        (
            {
                "n": _INPASA_PREFIX_RE.sub("", unit.name).strip(),
                "v": int(_round_half_up(unit.aderencia * 100)),
            }
            for unit in result.units
            if not unit.excluded
        ),
        key=lambda item: cast(int, item["v"]),
        reverse=True,
    )

    mensal = [
        {
            "label": month.label,
            "v": None if month.dias_medios is None else _round_half_up(month.dias_medios, 2),
        }
        for month in result.months
    ]

    ofensores: list[dict[str, str | float]] = [
        {"n": o.name, "pct": _round_half_up(o.pct * 1000) / 10} for o in top
    ]
    if outros_pct > _OUTROS_THRESHOLD:
        ofensores.append({"n": "Outros", "pct": _round_half_up(outros_pct * 1000) / 10})

    return {
        "pontos": RNC_SCORECARD_POINTS,
        "peso": RNC_SCORECARD_WEIGHT,
        "meta": result.meta_dias,
        "resultado": result.resultado_dias,
        "semestreResolvidas": result.total_tratadas,
        "semestreTotal": result.total_criadas,
        "periodo": _period_to_dict(result.period),
        "unidades": unidades,
        "mensal": mensal,
        "ofensores": ofensores,
    }
