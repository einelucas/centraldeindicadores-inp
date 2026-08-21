"""Cálculos puros do módulo RDO. Porte literal de
`src/features/rdo/calculations/index.ts` (migração fiel de `renderRdo()` do
HTML original). Nenhuma função aqui faz I/O — testável isoladamente.
"""

from __future__ import annotations

from app.modules.rdo.types import (
    RDO_DEFAULT_TARGET,
    STATUS_APROVADO,
    STATUS_PREENCHENDO,
    STATUS_REVISAR,
    RdoMonthAggregate,
    RdoNormalizedRecord,
    RdoResult,
    RdoUnitAggregate,
)
from app.shared.period import MONTH_NAMES, PeriodRange, is_within_period_range
from app.shared.units import normalize_unit_code

__all__ = ["calculate_rdo_adherence", "compute_rdo_result", "meets_target"]


def calculate_rdo_adherence(approved: int, issued: int) -> float:
    """Fração crua aprovados/emitidos, sem arredondamento. `0` se `issued==0`
    (evita divisão por zero)."""
    if issued == 0:
        return 0.0
    return approved / issued


def meets_target(adherence: float, threshold: float) -> bool:
    return adherence >= threshold


def _normalize_excluded(excluded_units: list[str]) -> list[str]:
    """`Array.from(new Set(excludedUnits.map(normalizeRdoUnitCode).filter(Boolean)))`
    — normaliza, remove vazios e deduplica preservando a ordem de 1ª ocorrência."""
    seen: list[str] = []
    for value in excluded_units:
        code = normalize_unit_code(value)
        if code and code not in seen:
            seen.append(code)
    return seen


def compute_rdo_result(
    records: list[RdoNormalizedRecord],
    threshold: float = RDO_DEFAULT_TARGET,
    excluded_units: list[str] | None = None,
    period: PeriodRange | None = None,
) -> RdoResult:
    """Função pura — mesma assinatura do TypeScript `computeRdoResult`.

    Duas semânticas de "exclusão" distintas e propositalmente preservadas:
    - corte de período: remove a linha de TODAS as tabelas, inclusive por
      unidade (Divergência #12);
    - unidade excluída: mantém a linha na tabela por unidade (`byUnit`),
      só removendo dos totais gerais e do agregado mensal.
    """
    excluded_normalized = _normalize_excluded(excluded_units or [])
    exclude_set = set(excluded_normalized)

    by_unit: dict[str, RdoUnitAggregate] = {}
    by_month: dict[str, RdoMonthAggregate] = {}

    total_emitidos = 0
    total_aprovados = 0
    total_revisar = 0
    total_preenchendo = 0

    for record in records:
        status = (record.status_descricao or "").strip()
        unit = normalize_unit_code(record.empresa_nome)

        # Filtro estrutural: precisa de data válida E unidade normalizada
        # não-vazia (equivale ao COUNTA da coluna data no HTML original).
        if record.data_referencia is None or not unit:
            continue

        year = record.data_referencia.year
        month0 = record.data_referencia.month - 1  # 0-based, como Date.getMonth()
        month1 = record.data_referencia.month  # 1-based

        # Corte de período: descarta a linha inteira, inclusive da tabela por unidade.
        if period is not None and not is_within_period_range(year, month1, period):
            continue

        unit_agg = by_unit.get(unit)
        if unit_agg is None:
            unit_agg = RdoUnitAggregate(
                name=unit, emitidos=0, aprovados=0, aderencia=0.0, excluded=unit in exclude_set
            )
            by_unit[unit] = unit_agg
        unit_agg.emitidos += 1
        if status == STATUS_APROVADO:
            unit_agg.aprovados += 1

        # Unidade excluída: a partir daqui a linha não entra mais em totais/meses.
        if unit in exclude_set:
            continue

        total_emitidos += 1
        if status == STATUS_APROVADO:
            total_aprovados += 1
        elif status == STATUS_REVISAR:
            total_revisar += 1
        elif status == STATUS_PREENCHENDO:
            total_preenchendo += 1
        # Qualquer outro texto de status não incrementa nenhum dos três
        # (Divergência #10) — ainda assim conta em total_emitidos.

        month_key = f"{year}-{month0 + 1:02d}"
        month_agg = by_month.get(month_key)
        if month_agg is None:
            month_agg = RdoMonthAggregate(
                year=year,
                month=month0,
                label=f"{MONTH_NAMES[month0]}/{year}",
                emitidos=0,
                aprovados=0,
                aderencia=0.0,
            )
            by_month[month_key] = month_agg
        month_agg.emitidos += 1
        if status == STATUS_APROVADO:
            month_agg.aprovados += 1

    units = sorted(by_unit.values(), key=lambda u: u.emitidos, reverse=True)
    for unit_agg in units:
        unit_agg.aderencia = calculate_rdo_adherence(unit_agg.aprovados, unit_agg.emitidos)

    # unitAvg: média aritmética simples das aderências das unidades NÃO excluídas
    # — não é ponderada por volume de emitidos.
    unit_avg_values = [u.aderencia for u in units if not u.excluded]
    unit_avg = sum(unit_avg_values) / len(unit_avg_values) if unit_avg_values else 0.0

    months = sorted(by_month.values(), key=lambda m: (m.year, m.month))
    for month_agg in months:
        month_agg.aderencia = calculate_rdo_adherence(month_agg.aprovados, month_agg.emitidos)

    return RdoResult(
        threshold=threshold,
        excluded_units=excluded_normalized,
        period=period,
        total_emitidos=total_emitidos,
        total_aprovados=total_aprovados,
        total_revisar=total_revisar,
        total_preenchendo=total_preenchendo,
        units=units,
        unit_avg=unit_avg,
        months=months,
    )
