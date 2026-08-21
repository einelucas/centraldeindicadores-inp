"""Cálculos puros do módulo RNC. Porte literal de
`src/features/rnc/calculations/index.ts` (`computeRncResult`).

Nenhuma função aqui faz I/O — testável isoladamente. Duas dualidades
propositalmente preservadas (ver Divergência #4 do inventário):

- "solucionada" a nível de MÊS (`RncMonthAggregate.solucionados`) usa a
  presença de `dataSolucao` válida, independente de `statusRnc`;
- "tratada" a nível de UNIDADE/TOTAL (`aderencia`, `totalTratadas`) usa
  estritamente `statusRnc.strip().upper() == "TRATADA"`.

Um mesmo registro pode contar como "solucionado" no mês mas não como
"tratado" na unidade (ou vice-versa) — os dois números resultantes podem
divergir. Não fundir os dois critérios.
"""

from __future__ import annotations

import math

from app.modules.rnc.types import (
    RNC_DEFAULT_MAX_DIAS,
    RNC_STATUS_TRATADA,
    RncMonthAggregate,
    RncNormalizedRecord,
    RncOfensorAggregate,
    RncResult,
    RncUnitAggregate,
)
from app.shared.period import MONTH_NAMES, PeriodRange, is_within_period_range
from app.shared.units import normalize_unit_code

__all__ = ["average_monthly_rnc_days", "compute_rnc_result", "median"]


def median(values: list[float]) -> float | None:
    """Mediana simples: ordena ascendente; ímpar -> elemento do meio; par ->
    média dos dois centrais. `None` para lista vazia."""
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def average_monthly_rnc_days(months: list[float | None]) -> float | None:
    """Média aritmética SIMPLES dos `diasMedios` válidos de cada mês — cada
    mês pesa 1, independentemente do volume de RNCs tratadas nele. Meses sem
    resultado válido (`None`) não entram na soma nem no denominador. NÃO é a
    média ponderada por volume (fórmula antiga, abandonada)."""
    valid = [v for v in months if v is not None and math.isfinite(v)]
    if not valid:
        return None
    return sum(valid) / len(valid)


def _normalize_excluded(excluded_units: list[str]) -> list[str]:
    seen: list[str] = []
    for value in excluded_units:
        code = normalize_unit_code(value)
        if code and code not in seen:
            seen.append(code)
    return seen


class _UnitAccum:
    __slots__ = ("criadas", "excluded", "name", "ofensores", "tempos_tratativa", "tratadas")

    def __init__(self, name: str, excluded: bool) -> None:
        self.name = name
        self.criadas = 0
        self.tratadas = 0
        self.tempos_tratativa: list[float] = []
        self.ofensores: dict[str, int] = {}
        self.excluded = excluded


class _MonthAccum:
    __slots__ = ("chamados", "month", "solucionados", "tratativa_count", "tratativa_sum", "year")

    def __init__(self, year: int, month0: int) -> None:
        self.year = year
        self.month = month0
        self.chamados = 0
        self.solucionados = 0
        self.tratativa_sum = 0.0
        self.tratativa_count = 0


def compute_rnc_result(
    records: list[RncNormalizedRecord],
    meta_dias: float = RNC_DEFAULT_MAX_DIAS,
    excluded_units: list[str] | None = None,
    period: PeriodRange | None = None,
) -> RncResult:
    """Função pura — mesma assinatura do TypeScript `computeRncResult`.

    Corte de período é ESTRUTURAL: remove o registro de TODA agregação
    (inclusive da tabela por unidade). Unidade excluída, ao contrário, mantém
    a linha na tabela por unidade (com `excluded=True`) — só some de
    total/mês/ofensor."""
    excluded_normalized = _normalize_excluded(excluded_units or [])
    exclude_set = set(excluded_normalized)

    by_unit: dict[str, _UnitAccum] = {}
    by_month: dict[str, _MonthAccum] = {}
    by_ofensor: dict[str, int] = {}

    total_criadas = 0
    total_tratadas = 0

    for record in records:
        if record.data_criacao is None:
            continue

        year = record.data_criacao.year
        month0 = record.data_criacao.month - 1
        month1 = record.data_criacao.month

        # Corte estrutural: fora do período selecionado, o registro nem
        # entra em nenhuma tabela.
        if period is not None and not is_within_period_range(year, month1, period):
            continue

        unit = normalize_unit_code(record.unidade)
        status = (record.status_rnc or "").strip()
        is_tratada = status.upper() == RNC_STATUS_TRATADA
        has_valid_solucao = record.data_solucao is not None
        has_numeric_tempo = record.tempo_tratativa is not None and math.isfinite(record.tempo_tratativa)
        ofensor_name = (record.ofensor or "").strip() or "N/A"

        if unit:
            unit_agg = by_unit.get(unit)
            if unit_agg is None:
                unit_agg = _UnitAccum(unit, unit in exclude_set)
                by_unit[unit] = unit_agg
            unit_agg.criadas += 1
            if is_tratada:
                unit_agg.tratadas += 1
            if has_valid_solucao and has_numeric_tempo:
                unit_agg.tempos_tratativa.append(record.tempo_tratativa)  # type: ignore[arg-type]
            unit_agg.ofensores[ofensor_name] = unit_agg.ofensores.get(ofensor_name, 0) + 1

        # Unidade excluída: a partir daqui a linha não entra mais em
        # totais/mês/ofensor global. `unit == ""` NUNCA é tratada como
        # excluída, mesmo que "" estivesse (por acidente) na lista.
        if unit and unit in exclude_set:
            continue

        total_criadas += 1
        if is_tratada:
            total_tratadas += 1

        month_key = f"{year}-{month0 + 1:02d}"
        month_agg = by_month.get(month_key)
        if month_agg is None:
            month_agg = _MonthAccum(year, month0)
            by_month[month_key] = month_agg
        month_agg.chamados += 1
        if has_valid_solucao:
            month_agg.solucionados += 1
            if has_numeric_tempo and record.tempo_tratativa is not None:
                month_agg.tratativa_sum += record.tempo_tratativa
                month_agg.tratativa_count += 1

        by_ofensor[ofensor_name] = by_ofensor.get(ofensor_name, 0) + 1

    units: list[RncUnitAggregate] = []
    for accum in by_unit.values():
        dias_medios = (
            sum(accum.tempos_tratativa) / len(accum.tempos_tratativa) if accum.tempos_tratativa else None
        )
        principal_ofensor: str | None = None
        principal_ofensor_count = 0
        if accum.ofensores:
            # Empate: contagem desc, depois ordem alfabética ascendente
            # (aproximação de `localeCompare("pt-BR")` — não reproduz
            # colação de acentos bit a bit, documentado como simplificação
            # aceita nas decisões da migração).
            name, count = sorted(accum.ofensores.items(), key=lambda kv: (-kv[1], kv[0]))[0]
            principal_ofensor, principal_ofensor_count = name, count

        units.append(
            RncUnitAggregate(
                name=accum.name,
                criadas=accum.criadas,
                tratadas=accum.tratadas,
                aderencia=(accum.tratadas / accum.criadas) if accum.criadas else 0.0,
                tempos_tratativa=accum.tempos_tratativa,
                dias_medios=dias_medios,
                dias_medianos=median(accum.tempos_tratativa),
                tratativas_com_tempo=len(accum.tempos_tratativa),
                maior_tempo_tratativa=max(accum.tempos_tratativa) if accum.tempos_tratativa else None,
                principal_ofensor=principal_ofensor,
                principal_ofensor_count=principal_ofensor_count,
                excluded=accum.excluded,
            )
        )
    units.sort(key=lambda u: u.criadas, reverse=True)

    months: list[RncMonthAggregate] = []
    for month_accum in by_month.values():
        dias_medios = (
            month_accum.tratativa_sum / month_accum.tratativa_count if month_accum.tratativa_count else None
        )
        months.append(
            RncMonthAggregate(
                year=month_accum.year,
                month=month_accum.month,
                label=f"{MONTH_NAMES[month_accum.month]}/{month_accum.year}",
                chamados=month_accum.chamados,
                solucionados=month_accum.solucionados,
                dias_medios=dias_medios,
                dentro_meta=None if dias_medios is None else dias_medios <= meta_dias,
            )
        )
    months.sort(key=lambda m: (m.year, m.month))

    total_ofensor = sum(by_ofensor.values())
    ofensores = [
        RncOfensorAggregate(name=name, count=count, pct=(count / total_ofensor if total_ofensor else 0.0))
        for name, count in sorted(by_ofensor.items(), key=lambda kv: kv[1], reverse=True)
    ]

    resultado_dias = average_monthly_rnc_days([m.dias_medios for m in months])
    aderencia_total = (total_tratadas / total_criadas) if total_criadas else 0.0

    return RncResult(
        meta_dias=meta_dias,
        excluded_units=excluded_normalized,
        period=period,
        total_criadas=total_criadas,
        total_tratadas=total_tratadas,
        aderencia_total=aderencia_total,
        resultado_dias=resultado_dias,
        months=months,
        units=units,
        ofensores=ofensores,
    )
