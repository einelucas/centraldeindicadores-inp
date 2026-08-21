"""Cálculos puros do módulo IDP/RSO. Porte literal de
`src/features/idp/calculations/index.ts`.

Nenhuma função aqui faz I/O — testável isoladamente. Duas normalizações de
unidade DIFERENTES convivem de propósito neste módulo (Divergência #4 do
inventário, preservada por instrução explícita do prompt de migração — "não
unificar"): `normalized_unit_key` (leve — maiúsculas/acentos/espaços, usada
na business key) e `app.shared.units.normalize_unit_code` (canônica — mapeia
para a sigla oficial da unidade, usada no versionamento/exclusões).
"""

from __future__ import annotations

import math
import re
import unicodedata

from app.models.common import utcnow
from app.modules.idp.types import (
    IDP_DISC_NAMES,
    IdpDisciplineRow,
    IdpMonthAggregate,
    IdpNormalizedRecord,
    IdpResult,
    IdpUnitRow,
)
from app.shared.dates import MONTH_NAMES_FULL
from app.shared.normalization import collapse_spaces
from app.shared.period import PeriodRange, enumerate_period_months, is_within_period_range
from app.shared.units import normalize_unit_code

__all__ = [
    "average_ignoring_none",
    "calculate_idp_adherence",
    "compute_idp_result",
    "is_idp_discipline_excluded",
    "normalize_idp_discipline_name",
    "normalized_unit_key",
    "records_in_competence",
    "select_latest_rso_by_unit",
]

_COMBINING_MARKS_RE = re.compile(r"[̀-ͯ]")
_UNDERSCORE_DASH_RE = re.compile(r"[_–—-]+")


def calculate_idp_adherence(real: float, previsto: float) -> float | None:
    """Aderência = realizado acumulado / previsto (linha de base) acumulado.

    **Divergência aplicada** (fonte 1 da hierarquia — regra explícita do
    prompt de migração, que tem precedência sobre o comportamento do `HEAD`):
    `previsto == 0` (ou não finito) retorna `None` (ausência de resultado
    válido), NÃO `0`. O TS original retorna `0` neste caso — ver
    `docs/backend-migration-decisions.md` §4.2.1."""
    if not math.isfinite(previsto) or previsto == 0:
        return None
    numerator = real if math.isfinite(real) else 0.0
    return numerator / previsto


def average_ignoring_none(values: list[float | None]) -> float | None:
    """Média simples ignorando `None` (ausência estrutural ou de baseline) —
    nunca trata ausência como zero. Mesmo padrão de
    `app.modules.rnc.calculations.average_monthly_rnc_days`."""
    valid = [v for v in values if v is not None and math.isfinite(v)]
    if not valid:
        return None
    return sum(valid) / len(valid)


def _mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def normalized_unit_key(value: object) -> str:
    """Normalização LEVE usada exclusivamente na business key
    (`normalizedUnitKey` do TS, `calculations/index.ts:62-69`): trim -> NFD
    -> remove diacríticos -> colapsa espaços -> maiúsculas. Diferente de
    `normalize_unit_code` — não mapeia para a sigla canônica da unidade."""
    text = collapse_spaces(str(value) if value is not None else "")
    text = unicodedata.normalize("NFD", text)
    text = _COMBINING_MARKS_RE.sub("", text)
    return collapse_spaces(text).upper()


def normalize_idp_discipline_name(value: object) -> str:
    text = collapse_spaces(str(value) if value is not None else "")
    text = unicodedata.normalize("NFD", text)
    text = _COMBINING_MARKS_RE.sub("", text)
    text = text.lower()
    text = _UNDERSCORE_DASH_RE.sub(" ", text)
    return collapse_spaces(text)


def is_idp_discipline_excluded(disciplina: str, excluded_disciplines: list[str]) -> bool:
    normalized = normalize_idp_discipline_name(disciplina)
    return any(normalize_idp_discipline_name(e) == normalized for e in excluded_disciplines)


def _tie_breaker_time(entry: IdpNormalizedRecord) -> float:
    """Tenta, nessa ordem, `updated_at` -> `emission_date` -> `period_end`;
    o primeiro valor presente e válido vence. `0.0` se nenhum estiver
    disponível."""
    for value in (entry.updated_at, entry.emission_date, entry.period_end):
        if value is not None:
            return value.timestamp()
    return 0.0


def records_in_competence(
    entries: list[IdpNormalizedRecord], year: int, month: int
) -> list[IdpNormalizedRecord]:
    return [e for e in entries if e.reference_year == year and e.reference_month == month]


def select_latest_rso_by_unit(entries: list[IdpNormalizedRecord]) -> list[IdpNormalizedRecord]:
    """Agrupa por `normalize_unit_code(unit)` (código canônico — NÃO a
    normalização leve da business key). Vence o maior `rso_numero`; empate
    (mesmo número) é resolvido por `_tie_breaker_time`. Versões antigas
    permanecem no banco mas não entram em nenhuma agregação a partir daqui."""
    latest_by_unit: dict[str, IdpNormalizedRecord] = {}
    for entry in entries:
        unit_key = normalize_unit_code(entry.unit)
        if not unit_key:
            continue
        current = latest_by_unit.get(unit_key)
        if current is None:
            latest_by_unit[unit_key] = entry
            continue
        if entry.rso_numero > current.rso_numero or (
            entry.rso_numero == current.rso_numero
            and _tie_breaker_time(entry) > _tie_breaker_time(current)
        ):
            latest_by_unit[unit_key] = entry
    return sorted(latest_by_unit.values(), key=lambda e: e.unit)


def _to_unit_row(entry: IdpNormalizedRecord, exclude_unit_set: set[str]) -> IdpUnitRow:
    prev_values = [p.prev_acum for p in entry.execucao_fases]
    real_values = [p.real_acum for p in entry.execucao_fases]
    prev_acum = sum(prev_values) / len(prev_values) if prev_values else 0.0
    real_acum = sum(real_values) / len(real_values) if real_values else 0.0
    aderencia = calculate_idp_adherence(real_acum, prev_acum) if prev_values else None

    return IdpUnitRow(
        source_id=entry.id,
        unit=entry.unit,
        rso_numero=entry.rso_numero,
        reference_year=entry.reference_year,
        reference_month=entry.reference_month,
        reference_source=entry.reference_source,
        reference_original_text=entry.reference_original_text,
        reference_adjusted=entry.reference_adjusted,
        period_start=entry.period_start,
        period_end=entry.period_end,
        emission_date=entry.emission_date,
        file_name=entry.file_name,
        n_fases=len(entry.execucao_fases),
        prev_acum=prev_acum,
        real_acum=real_acum,
        aderencia=aderencia,
        excluded=normalize_unit_code(entry.unit) in exclude_unit_set,
        phases=list(entry.execucao_fases),
    )


def _build_discipline_rows(
    included_winners: list[IdpNormalizedRecord], excluded_disciplines: list[str]
) -> list[IdpDisciplineRow]:
    rows: list[IdpDisciplineRow] = []
    for disciplina in IDP_DISC_NAMES:
        if is_idp_discipline_excluded(disciplina, excluded_disciplines):
            continue
        prev_values: list[float] = []
        real_values: list[float] = []
        for entry in included_winners:
            for area_entry in entry.disc_data.get(disciplina, []):
                prev_values.append(area_entry.prev_acum)
                real_values.append(area_entry.real_acum)
        prev_avg = _mean_or_none(prev_values)
        real_avg = _mean_or_none(real_values)
        aderencia = None
        if prev_avg is not None and real_avg is not None:
            aderencia = calculate_idp_adherence(real_avg, prev_avg)
        rows.append(
            IdpDisciplineRow(disciplina=disciplina, prev_avg=prev_avg, real_avg=real_avg, aderencia=aderencia)
        )
    return rows


def _latest_competence(records: list[IdpNormalizedRecord]) -> tuple[int, int] | None:
    if not records:
        return None
    return max((r.reference_year, r.reference_month) for r in records)


def _resolve_selected_and_history(
    records: list[IdpNormalizedRecord], period: PeriodRange | None
) -> tuple[int, int, int, int, int, int]:
    """Retorna `(selected_year, selected_month, history_start_year,
    history_month_start, history_end_year, history_month_end)`.

    Com período: a competência selecionada é a mais recente DENTRO do
    intervalo; se nenhuma existir, cai no fim do intervalo (resultado
    zerado) — nunca escapa para um mês fora do período pedido. Sem período
    (`GET /idp` sem filtro): usa a competência mais recente disponível em
    toda a base como único mês do "histórico"; sem nenhum registro, usa o
    mês/ano atual. Este último ramo (sem período) não tem um caso de teste
    unitário correspondente no TS original — decisão pragmática documentada
    em `docs/backend-migration-decisions.md` §4.2.2."""
    if period is not None:
        in_range = [r for r in records if is_within_period_range(r.reference_year, r.reference_month, period)]
        latest = _latest_competence(in_range)
        selected_year, selected_month = latest if latest is not None else (period.end_year, period.end_month)
        return (
            selected_year, selected_month,
            period.start_year, period.start_month, period.end_year, period.end_month,
        )

    latest = _latest_competence(records)
    if latest is not None:
        selected_year, selected_month = latest
    else:
        now = utcnow()
        selected_year, selected_month = now.year, now.month
    return (selected_year, selected_month, selected_year, selected_month, selected_year, selected_month)


def _build_monthly(
    records: list[IdpNormalizedRecord],
    excluded_disciplines: list[str],
    exclude_unit_set: set[str],
    history: PeriodRange,
) -> list[IdpMonthAggregate]:
    months: list[IdpMonthAggregate] = []
    for ref in enumerate_period_months(history):
        winners = select_latest_rso_by_unit(records_in_competence(records, ref.year, ref.month))
        rows = [_to_unit_row(e, exclude_unit_set) for e in winners]
        included = [u for u in rows if not u.excluded]
        months.append(
            IdpMonthAggregate(
                year=ref.year,
                month=ref.month,
                label=f"{MONTH_NAMES_FULL[ref.month - 1]}/{ref.year}",
                aderencia=average_ignoring_none([u.aderencia for u in included]),
                active_documents=len(rows),
                total_previsto_medio=sum(u.prev_acum for u in included),
                total_real_medio=sum(u.real_acum for u in included),
            )
        )
    return months


def _normalize_excluded_units(excluded_units: list[str]) -> list[str]:
    seen: list[str] = []
    for value in excluded_units:
        code = normalize_unit_code(value)
        if code and code not in seen:
            seen.append(code)
    return seen


def compute_idp_result(
    records: list[IdpNormalizedRecord],
    threshold: float,
    excluded_disciplines: list[str] | None = None,
    excluded_units: list[str] | None = None,
    period: PeriodRange | None = None,
) -> IdpResult:
    """Função pura — mesma assinatura conceitual do TypeScript
    `computeIdpResult`. `excluded_disciplines`/`excluded_units` já devem vir
    resolvidos pelo chamador (defaults de configuração aplicados fora
    desta função, mesmo padrão de RDO/RNC/5S)."""
    excluded_disciplines_list = list(excluded_disciplines or [])
    excluded_units_normalized = _normalize_excluded_units(excluded_units or [])
    exclude_unit_set = set(excluded_units_normalized)

    (
        selected_year, selected_month,
        history_start_year, history_month_start,
        history_end_year, history_month_end,
    ) = _resolve_selected_and_history(records, period)

    winners = select_latest_rso_by_unit(records_in_competence(records, selected_year, selected_month))
    unit_rows = [_to_unit_row(e, exclude_unit_set) for e in winners]
    included_unit_rows = [u for u in unit_rows if not u.excluded]

    included_winner_entries = [
        e for e in winners if normalize_unit_code(e.unit) not in exclude_unit_set
    ]
    discipline_rows = _build_discipline_rows(included_winner_entries, excluded_disciplines_list)

    history = PeriodRange(
        start_year=history_start_year, start_month=history_month_start,
        end_year=history_end_year, end_month=history_month_end,
    )
    monthly = _build_monthly(records, excluded_disciplines_list, exclude_unit_set, history)

    return IdpResult(
        threshold=threshold,
        excluded_disciplines=excluded_disciplines_list,
        excluded_units=excluded_units_normalized,
        selected_year=selected_year,
        selected_month=selected_month,
        history_start_year=history_start_year,
        history_month_start=history_month_start,
        history_end_year=history_end_year,
        history_month_end=history_month_end,
        active_documents=len(unit_rows),
        aderencia_geral=average_ignoring_none([u.aderencia for u in included_unit_rows]),
        total_previsto_medio=sum(u.prev_acum for u in included_unit_rows),
        total_real_medio=sum(u.real_acum for u in included_unit_rows),
        unit_rows=unit_rows,
        discipline_rows=discipline_rows,
        monthly=monthly,
    )
