"""Payload de publicação do 5S. Porte literal de
`src/features/cinco-s/publications/index.ts`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.modules.cinco_s.types import FIVES_SCORECARD_POINTS, FIVES_SCORECARD_WEIGHT, FiveSResult
from app.shared.period import PeriodRange


class FiveSPublicationError(Exception):
    """Levantado quando o último período não possui unidades elegíveis para
    publicação — equivalente ao `throw new Error(...)` de
    `toFiveSPublishedPayload`."""


@dataclass(frozen=True, slots=True)
class FiveSPublishedUnit:
    n: str  # sigla da unidade
    v: float  # aderência em percentual (0-100)


@dataclass(frozen=True, slots=True)
class FiveSPublishedMonth:
    label: str  # ex.: "Jun/2026"
    v: float  # GERAL em percentual (0-100)
    units: int


@dataclass(frozen=True, slots=True)
class FiveSPublishedPayload:
    pontos: float
    peso: float
    meta: float  # percentual 0-100
    resultado: float  # percentual 0-100 (aderência do último mês)
    reference_year: int
    reference_month: int
    excluded_units: list[str]
    periodo: PeriodRange | None
    unidades: list[FiveSPublishedUnit]  # último mês, unidades incluídas, desc por valor
    mensal: list[FiveSPublishedMonth]  # série histórica só com meses reais


def to_five_s_published_payload(result: FiveSResult) -> FiveSPublishedPayload:
    """Converte somente o resultado calculado com registros reais."""
    if result.geral is None or result.latest_year is None or result.latest_month is None:
        raise FiveSPublicationError("O último período não possui unidades elegíveis para publicação.")

    unidades = sorted(
        (
            FiveSPublishedUnit(n=item.unit, v=item.aderencia * 100)
            for item in result.unit_months
            if item.year == result.latest_year and item.month == result.latest_month and not item.excluded
        ),
        key=lambda unit: unit.v,
        reverse=True,
    )
    mensal = [
        FiveSPublishedMonth(label=month.label, v=(month.geral or 0) * 100, units=month.units_count)
        for month in result.months
        if month.geral is not None
    ]

    return FiveSPublishedPayload(
        pontos=FIVES_SCORECARD_POINTS,
        peso=FIVES_SCORECARD_WEIGHT,
        meta=result.threshold * 100,
        resultado=result.geral * 100,
        reference_year=result.latest_year,
        reference_month=result.latest_month,
        excluded_units=result.excluded_units,
        periodo=result.period,
        unidades=unidades,
        mensal=mensal,
    )


def five_s_published_payload_to_json(payload: FiveSPublishedPayload) -> dict[str, Any]:
    """Serializa o payload para o formato JSON exato persistido em
    `IndicatorPublication.payload` (mesmas chaves do objeto TS original)."""
    return {
        "pontos": payload.pontos,
        "peso": payload.peso,
        "meta": payload.meta,
        "resultado": payload.resultado,
        "referenceYear": payload.reference_year,
        "referenceMonth": payload.reference_month,
        "excludedUnits": payload.excluded_units,
        "periodo": (
            {
                "startYear": payload.periodo.start_year,
                "startMonth": payload.periodo.start_month,
                "endYear": payload.periodo.end_year,
                "endMonth": payload.periodo.end_month,
            }
            if payload.periodo is not None
            else None
        ),
        "unidades": [{"n": unit.n, "v": unit.v} for unit in payload.unidades],
        "mensal": [{"label": month.label, "v": month.v, "units": month.units} for month in payload.mensal],
    }
