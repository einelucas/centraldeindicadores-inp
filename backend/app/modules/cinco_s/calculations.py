"""Cálculos do 5S. Funções puras — porte literal de
`src/features/cinco-s/calculations/index.ts`.

Regras preservadas (ver também `app/modules/cinco_s/types.py`):
  - Aderência de área = clamp(nota/meta, 0, 1). `meta` <= 0 ou não finita, ou
    `nota` não finita -> aderência = 0.
  - Aderência da unidade/mês = média simples das aderências de área.
  - GERAL do mês = média simples das unidades NÃO excluídas com dados no mês.
    Unidades excluídas não entram nem no numerador nem no denominador — nunca
    são substituídas por zero. Se todas as unidades do mês estiverem
    excluídas (ou não houver unidades), `geral = None`.
  - Resultado atual (`geral` do `FiveSResult`) = GERAL do ÚLTIMO mês
    realmente presente no array já ordenado — o algoritmo NUNCA recua para um
    mês anterior com dado válido, mesmo que o último mês tenha `geral=None`.
"""

from __future__ import annotations

import math
from dataclasses import replace
from functools import cmp_to_key

from app.modules.cinco_s.types import (
    FIVE_S_DEFAULT_TARGET,
    FiveSArea,
    FiveSMonthResult,
    FiveSNormalizedRecord,
    FiveSResult,
    FiveSUnitMonth,
)
from app.shared.period import MONTH_NAMES, PeriodRange, is_within_period_range
from app.shared.units import compare_units, normalize_unit_code


def _is_finite_number(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if not isinstance(value, int | float):
        return False
    return math.isfinite(value)


def aderencia_area(area: FiveSArea) -> float:
    """Aderência de uma área: clamp(nota/meta, 0, 1)."""
    if not _is_finite_number(area.meta) or area.meta <= 0:
        return 0.0
    if not _is_finite_number(area.nota):
        return 0.0
    return min(max(area.nota / area.meta, 0.0), 1.0)


def aderencia_unidade(areas: list[FiveSArea]) -> float:
    """Aderência média de uma unidade a partir de suas áreas reais."""
    if not areas:
        return 0.0
    return sum(aderencia_area(area) for area in areas) / len(areas)


def _month_key(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


def _month_label(year: int, month: int) -> str:
    name = MONTH_NAMES[month - 1] if 1 <= month <= 12 else str(month)
    return f"{name}/{year}"


def compute_five_s_result(
    records: list[FiveSNormalizedRecord],
    excluded: list[str] | None = None,
    threshold: float = FIVE_S_DEFAULT_TARGET,
    period: PeriodRange | None = None,
) -> FiveSResult:
    excluded_units = list(
        dict.fromkeys(code for code in (normalize_unit_code(item) for item in (excluded or [])) if code)
    )
    exclude_set = set(excluded_units)

    # A identidade lógica do módulo é unidade + ano + mês. Em caso de
    # registros repetidos no array, a última ocorrência representa a versão
    # mais recente (bases antigas podem ter nome completo e sigla para o
    # mesmo mês).
    unique: dict[str, tuple[FiveSNormalizedRecord, bool]] = {}
    for record in records:
        unit = normalize_unit_code(record.unit)
        if not unit or not record.areas:
            continue
        if not isinstance(record.year, int) or not isinstance(record.month, int):
            continue
        if record.month < 1 or record.month > 12:
            continue
        # Corte estrutural: fora do período selecionado, o registro nem
        # entra em nenhuma tabela. Sem período definido, nada é restringido.
        if period is not None and not is_within_period_range(record.year, record.month, period):
            continue

        key = f"{unit}|||{_month_key(record.year, record.month)}"
        uses_official_code = record.unit.strip().upper() == unit
        previous = unique.get(key)

        # A versão já gravada com a sigla oficial tem prioridade; entre
        # registros equivalentes, a última ocorrência representa a correção
        # mais recente.
        if previous is None or uses_official_code or not previous[1]:
            unique[key] = (replace(record, unit=unit), uses_official_code)

    unit_months: list[FiveSUnitMonth] = [
        FiveSUnitMonth(
            unit=rec.unit,
            year=rec.year,
            month=rec.month,
            aderencia=aderencia_unidade(rec.areas),
            excluded=rec.unit in exclude_set,
            areas=rec.areas,
        )
        for rec, _ in unique.values()
    ]

    def _compare(a: FiveSUnitMonth, b: FiveSUnitMonth) -> int:
        if a.year != b.year:
            return a.year - b.year
        if a.month != b.month:
            return a.month - b.month
        return compare_units(a.unit, b.unit)

    unit_months.sort(key=cmp_to_key(_compare))

    month_keys = sorted({_month_key(item.year, item.month) for item in unit_months})

    months: list[FiveSMonthResult] = []
    for key in month_keys:
        year_text, month_text = key.split("-")
        year, month = int(year_text), int(month_text)
        values = [
            item.aderencia
            for item in unit_months
            if item.year == year and item.month == month and not item.excluded
        ]
        geral = sum(values) / len(values) if values else None
        months.append(
            FiveSMonthResult(
                year=year, month=month, label=_month_label(year, month), geral=geral, units_count=len(values)
            )
        )

    latest = months[-1] if months else None
    geral = latest.geral if latest is not None else None

    return FiveSResult(
        threshold=threshold,
        excluded_units=excluded_units,
        period=period,
        period_label=latest.label if latest is not None else "—",
        latest_year=latest.year if latest is not None else None,
        latest_month=latest.month if latest is not None else None,
        geral=geral,
        passa_meta=geral is not None and geral >= threshold,
        unit_months=unit_months,
        months=months,
        units_count=len({item.unit for item in unit_months}),
        months_count=len(months),
    )
