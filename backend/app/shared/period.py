"""Período operacional compartilhado por todos os módulos.

Porte literal de `src/lib/period.ts` (Next.js). Único ponto de verdade para a
classificação de uma competência mensal (ano-calendário + mês) no semestre
operacional da empresa. NÃO reimplementar esta regra em outro lugar.

Regra oficial:
  - dezembro pertence ao S1 do ano SEGUINTE (ex.: Dez/2026 -> 2027 S1);
  - janeiro a maio pertencem ao S1 do próprio ano (ex.: Mar/2027 -> 2027 S1);
  - junho a novembro pertencem ao S2 do próprio ano (ex.: Ago/2027 -> 2027 S2).

Para S1, o "ano do período" é sempre o ano de TÉRMINO (maio), nunca o de
início (dezembro do ano anterior). Ex.: cycle_from_year_semester(2027, "S1")
= Dez/2026 - Mai/2027.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.sql.elements import ColumnElement

MONTH_NAMES = [
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
]

MONTH_NAMES_FULL = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


class Semester(str, Enum):
    S1 = "S1"
    S2 = "S2"


@dataclass(frozen=True, slots=True)
class PeriodRange:
    start_year: int
    start_month: int  # 1-12
    end_year: int
    end_month: int  # 1-12


@dataclass(frozen=True, slots=True)
class MonthReference:
    year: int
    month: int


@dataclass(frozen=True, slots=True)
class OperationalPeriod:
    period_year: int
    semester: Semester


def to_month_index(year: int, month: int) -> int:
    return year * 12 + (month - 1)


def _from_month_index(index: int) -> MonthReference:
    return MonthReference(year=index // 12, month=(index % 12) + 1)


def normalize_period_range(period_range: PeriodRange) -> PeriodRange:
    """Troca início/fim se o intervalo estiver invertido."""
    start_idx = to_month_index(period_range.start_year, period_range.start_month)
    end_idx = to_month_index(period_range.end_year, period_range.end_month)
    if start_idx <= end_idx:
        return period_range
    return PeriodRange(
        start_year=period_range.end_year,
        start_month=period_range.end_month,
        end_year=period_range.start_year,
        end_month=period_range.start_month,
    )


def is_within_period_range(year: int, month: int, period_range: PeriodRange | None) -> bool:
    """`True` sempre que `period_range` for `None` (nenhuma restrição = "Tudo")."""
    if period_range is None:
        return True
    normalized = normalize_period_range(period_range)
    idx = to_month_index(year, month)
    return (
        to_month_index(normalized.start_year, normalized.start_month)
        <= idx
        <= to_month_index(normalized.end_year, normalized.end_month)
    )


def enumerate_period_months(period_range: PeriodRange) -> list[MonthReference]:
    """Lista ordenada de {year, month} do início ao fim do intervalo, inclusive."""
    normalized = normalize_period_range(period_range)
    start_idx = to_month_index(normalized.start_year, normalized.start_month)
    end_idx = to_month_index(normalized.end_year, normalized.end_month)
    return [_from_month_index(idx) for idx in range(start_idx, end_idx + 1)]


def get_operational_period(year: int, month: int) -> OperationalPeriod:
    if not (1 <= month <= 12):
        raise ValueError("Competência mensal inválida.")
    if month == 12:
        return OperationalPeriod(period_year=year + 1, semester=Semester.S1)
    if month <= 5:
        return OperationalPeriod(period_year=year, semester=Semester.S1)
    return OperationalPeriod(period_year=year, semester=Semester.S2)


def cycle_from_year_semester(period_year: int, semester: Semester) -> PeriodRange:
    if semester == Semester.S2:
        return PeriodRange(
            start_year=period_year, start_month=6, end_year=period_year, end_month=11
        )
    return PeriodRange(
        start_year=period_year - 1, start_month=12, end_year=period_year, end_month=5
    )


def year_semester_from_cycle(cycle: PeriodRange) -> OperationalPeriod:
    semester = Semester.S1 if cycle.start_month == 12 else Semester.S2
    return OperationalPeriod(period_year=cycle.end_year, semester=semester)


def cycle_for_month(year: int, month: int) -> PeriodRange:
    op = get_operational_period(year, month)
    return cycle_from_year_semester(op.period_year, op.semester)


def get_current_cycle(reference: date | None = None) -> PeriodRange:
    ref = reference or date.today()
    return cycle_for_month(ref.year, ref.month)


def next_period(period_year: int, semester: Semester) -> OperationalPeriod:
    if semester == Semester.S1:
        return OperationalPeriod(period_year=period_year, semester=Semester.S2)
    return OperationalPeriod(period_year=period_year + 1, semester=Semester.S1)


def format_period_option_label(period_year: int, semester: Semester) -> str:
    cycle = cycle_from_year_semester(period_year, semester)
    start = f"{MONTH_NAMES[cycle.start_month - 1]}/{str(cycle.start_year)[-2:]}"
    end = f"{MONTH_NAMES[cycle.end_month - 1]}/{str(cycle.end_year)[-2:]}"
    return f"{period_year} {semester.value} · {start} - {end}"


def available_cycles_from_months(months: list[MonthReference]) -> list[PeriodRange]:
    """Somente ciclos com ao menos uma competência real, sem duplicidade, do mais recente ao mais antigo."""
    cycles: dict[tuple[int, int], PeriodRange] = {}
    for item in months:
        if not (1 <= item.month <= 12):
            continue
        cycle = cycle_for_month(item.year, item.month)
        cycles[(cycle.start_year, cycle.start_month)] = cycle
    return sorted(
        cycles.values(),
        key=lambda c: to_month_index(c.start_year, c.start_month),
        reverse=True,
    )


def format_period_range_label(
    period_range: PeriodRange | None, month_names: list[str] | None = None
) -> str:
    names = month_names or MONTH_NAMES
    if period_range is None:
        return "Tudo"
    normalized = normalize_period_range(period_range)
    start = f"{names[normalized.start_month - 1]}/{normalized.start_year}"
    end = f"{names[normalized.end_month - 1]}/{normalized.end_year}"
    return f"{start} – {end}"


def period_range_where(
    period_range: PeriodRange, year_field: str = "year", month_field: str = "month"
) -> tuple[str, dict[str, int]]:
    """Fragmento SQL (WHERE) equivalente a `is_within_period_range`.

    Retorna (sql_fragment, params) para uso com `text()` do SQLAlchemy.
    Inclusive nos dois extremos, atravessando a virada do ano civil quando
    necessário. Use nomes de parâmetro únicos ao compor múltiplas cláusulas.
    """
    normalized = normalize_period_range(period_range)
    sql = (
        f"(({year_field} > :period_start_year) "
        f"OR ({year_field} = :period_start_year AND {month_field} >= :period_start_month)) "
        f"AND (({year_field} < :period_end_year) "
        f"OR ({year_field} = :period_end_year AND {month_field} <= :period_end_month))"
    )
    params = {
        "period_start_year": normalized.start_year,
        "period_start_month": normalized.start_month,
        "period_end_year": normalized.end_year,
        "period_end_month": normalized.end_month,
    }
    return sql, params


def period_range_predicate(
    period_range: PeriodRange, year_col: Any, month_col: Any
) -> ColumnElement[bool]:
    """Equivalente ORM (SQLAlchemy ColumnElement) de `is_within_period_range`,
    para uso direto em `.where(...)` sem SQL textual."""
    from sqlalchemy import and_, or_

    normalized = normalize_period_range(period_range)
    return and_(
        or_(
            year_col > normalized.start_year,
            and_(year_col == normalized.start_year, month_col >= normalized.start_month),
        ),
        or_(
            year_col < normalized.end_year,
            and_(year_col == normalized.end_year, month_col <= normalized.end_month),
        ),
    )
