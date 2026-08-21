"""Cálculos puros da Taxa de Acidentes — sem I/O, testável isoladamente.

Porte literal de `src/features/taxa-acidentes/calculations/index.ts`
(`computeAccidentRateResult`). Regras do indicador (comentário original):

- o mesmo ano/mês é substituído pela última ocorrência;
- resultado do período = média aritmética de todos os meses carregados;
- acidentes CAF mensais = soma do período;
- desempenho do mês = taxa do período cronologicamente mais recente;
- quanto menor a taxa, melhor; atende quando resultado <= meta;
- os registros por unidade guardam as quantidades de acidentes CAF e SAF
  separadas por competência.

`rate` é digitado diretamente pelo usuário (nunca calculado a partir de
`caf`/`saf`) — esta função só consome o valor já gravado para tirar a média.
"""

from __future__ import annotations

import functools

from app.modules.taxa_acidentes.types import (
    AccidentMonthlyInput,
    AccidentMonthlyResult,
    AccidentRateResult,
    AccidentUnitInput,
    AccidentUnitResult,
)
from app.shared.period import MONTH_NAMES_FULL, PeriodRange, is_within_period_range
from app.shared.units import compare_units, normalize_unit_code


def month_label(year: int, month: int) -> str:
    """Ex.: `month_label(2026, 2) == "Fevereiro/2026"`."""
    name = MONTH_NAMES_FULL[month - 1] if 1 <= month <= 12 else str(month)
    return f"{name}/{year}"


def _unit_sort_cmp(a: AccidentUnitInput, b: AccidentUnitInput) -> int:
    if a.year != b.year:
        return a.year - b.year
    if a.month != b.month:
        return a.month - b.month
    return compare_units(a.unit, b.unit)


def sort_unit_inputs(units: list[AccidentUnitInput]) -> list[AccidentUnitInput]:
    """Ordena por competência (ano, mês) e depois pela ordem operacional
    oficial das unidades (`compare_units`) — não ordem alfabética."""
    return sorted(units, key=functools.cmp_to_key(_unit_sort_cmp))


def compute_accident_rate_result(
    monthly_records: list[AccidentMonthlyInput],
    unit_records: list[AccidentUnitInput],
    target: float,
    excluded_units: list[str] | None = None,
    period: PeriodRange | None = None,
) -> AccidentRateResult:
    excluded_units = excluded_units or []
    excluded_normalized: list[str] = []
    for raw in excluded_units:
        code = normalize_unit_code(raw)
        if code and code not in excluded_normalized:
            excluded_normalized.append(code)
    exclude_set = set(excluded_normalized)

    # Deduplicação mensal: mesma competência (year, month) é substituída pela
    # última ocorrência da lista de entrada (equivalente a `Map.set`).
    month_by_key: dict[str, AccidentMonthlyInput] = {}
    for record in monthly_records:
        if not is_within_period_range(record.year, record.month, period):
            continue
        key = f"{record.year}-{record.month:02d}"
        month_by_key[key] = record

    monthly_sorted = sorted(month_by_key.values(), key=lambda r: (r.year, r.month))
    monthly = [
        AccidentMonthlyResult(
            id=record.id,
            year=record.year,
            month=record.month,
            rate=record.rate,
            caf=record.caf,
            label=month_label(record.year, record.month),
            ok=record.rate <= target,
        )
        for record in monthly_sorted
    ]

    latest = monthly[-1] if monthly else None
    result = sum(record.rate for record in monthly) / len(monthly) if monthly else None
    total_caf = sum(record.caf for record in monthly)

    units_in_period = [
        record for record in unit_records if is_within_period_range(record.year, record.month, period)
    ]
    units_normalized = [
        AccidentUnitInput(
            year=record.year,
            month=record.month,
            unit=normalize_unit_code(record.unit),
            unit_key=record.unit_key,
            saf=record.saf,
            caf=record.caf,
            id=record.id,
        )
        for record in units_in_period
    ]
    units_sorted = sort_unit_inputs(units_normalized)
    units = [
        AccidentUnitResult(
            id=record.id,
            year=record.year,
            month=record.month,
            unit=record.unit,
            unit_key=record.unit_key,
            saf=record.saf,
            caf=record.caf,
            label=month_label(record.year, record.month),
            excluded=record.unit in exclude_set,
        )
        for record in units_sorted
    ]
    included_units = [unit for unit in units if not unit.excluded]

    return AccidentRateResult(
        target=target,
        excluded_units=excluded_normalized,
        period=period,
        result=result,
        total_caf=total_caf,
        total_unit_caf=sum(unit.caf for unit in included_units),
        total_saf=sum(unit.saf for unit in included_units),
        latest_rate=latest.rate if latest else None,
        latest_year=latest.year if latest else None,
        latest_month=latest.month if latest else None,
        months_count=len(monthly),
        monthly=monthly,
        units=units,
    )
