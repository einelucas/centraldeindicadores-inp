"""Resolução de ciclo de publicação (Ano + Semestre) a partir de um período.

Porte de `src/server/publications/cycle.ts` e
`src/server/publications/period-selection.ts`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, TypeGuard, TypeVar

from app.shared.period import (
    PeriodRange,
    Semester,
    cycle_from_year_semester,
    normalize_period_range,
)


@dataclass(frozen=True, slots=True)
class PublicationCycle:
    year: int
    semester: Semester


def resolve_publication_cycle(period: PeriodRange | None) -> PublicationCycle | None:
    """Só resolve um ciclo quando o período bate EXATAMENTE com um semestre
    operacional inteiro — nunca com um range parcial/arbitrário."""
    if period is None:
        return None
    normalized = normalize_period_range(period)

    for candidate in (
        PublicationCycle(year=normalized.start_year, semester=Semester.S2),
        PublicationCycle(year=normalized.end_year, semester=Semester.S1),
    ):
        cycle = cycle_from_year_semester(candidate.year, candidate.semester)
        if (
            cycle.start_year == normalized.start_year
            and cycle.start_month == normalized.start_month
            and cycle.end_year == normalized.end_year
            and cycle.end_month == normalized.end_month
        ):
            return candidate
    return None


def _is_period_range_dict(value: Any) -> TypeGuard[dict[str, int]]:
    if not isinstance(value, dict):
        return False
    keys = ("startYear", "startMonth", "endYear", "endMonth")
    return all(isinstance(value.get(k), int) for k in keys)


def publication_period_from_payload(payload: Any) -> PeriodRange | None:
    """Resolve o intervalo gravado no campo `periodo` de um payload publicado."""
    if not isinstance(payload, dict):
        return None
    period = payload.get("periodo")
    if _is_period_range_dict(period):
        return normalize_period_range(
            PeriodRange(
                start_year=period["startYear"],
                start_month=period["startMonth"],
                end_year=period["endYear"],
                end_month=period["endMonth"],
            )
        )
    return None


def periods_match(a: PeriodRange, b: PeriodRange) -> bool:
    left, right = normalize_period_range(a), normalize_period_range(b)
    return (
        left.start_year == right.start_year
        and left.start_month == right.start_month
        and left.end_year == right.end_year
        and left.end_month == right.end_month
    )


class PublicationWithCycle(Protocol):
    active: bool
    payload: Any
    cycleYear: int | None
    cycleSemester: str | None
    periodStartYear: int | None
    periodStartMonth: int | None
    periodEndYear: int | None
    periodEndMonth: int | None


def publication_cycle_period(publication: PublicationWithCycle) -> PeriodRange | None:
    """Prioriza as colunas dedicadas de ciclo; cai para `payload.periodo`
    apenas quando as colunas são nulas (publicações antigas)."""
    if (
        publication.periodStartYear is not None
        and publication.periodStartMonth is not None
        and publication.periodEndYear is not None
        and publication.periodEndMonth is not None
    ):
        return normalize_period_range(
            PeriodRange(
                start_year=publication.periodStartYear,
                start_month=publication.periodStartMonth,
                end_year=publication.periodEndYear,
                end_month=publication.periodEndMonth,
            )
        )
    return publication_period_from_payload(publication.payload)


_TPub = TypeVar("_TPub", bound=PublicationWithCycle)


def select_publication_for_period(
    publications: list[_TPub], requested_period: PeriodRange | None
) -> tuple[_TPub | None, int]:
    """Retorna (publication | None, history_count)."""
    history_count = sum(1 for p in publications if publication_cycle_period(p) is not None)

    if requested_period is not None:
        publication = next(
            (
                p
                for p in publications
                if (period := publication_cycle_period(p)) is not None
                and periods_match(period, requested_period)
            ),
            None,
        )
    else:
        publication = next((p for p in publications if p.active), None)

    return publication, history_count
