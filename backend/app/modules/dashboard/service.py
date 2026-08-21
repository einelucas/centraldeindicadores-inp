"""Orquestração do Painel Geral — resolve o período efetivo (query > período
salvo em `AppSetting` > ciclo vigente), carrega publicações + snapshots e
delega o consolidado para `scorecard.calculations.compute_general_panel`.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scorecard import repository as scorecard_repository
from app.modules.scorecard.calculations import (
    GeneralPanelData,
    adapt_publication,
    compute_general_panel,
    read_snapshot_values,
)
from app.modules.scorecard.types import SC_INDICATORS
from app.shared.period import (
    MonthReference,
    PeriodRange,
    available_cycles_from_months,
    format_period_option_label,
    get_current_cycle,
    is_within_period_range,
    year_semester_from_cycle,
)


async def resolve_effective_period(
    session: AsyncSession, requested: PeriodRange | None
) -> PeriodRange:
    """Query > `AppSetting["scorecard.panelPeriod"]` salvo > ciclo vigente."""
    if requested is not None:
        return requested
    saved = await scorecard_repository.get_panel_period(session)
    if saved is not None:
        return saved
    return get_current_cycle()


async def get_general_panel(session: AsyncSession, period: PeriodRange) -> GeneralPanelData:
    publications = await scorecard_repository.list_all_source_publications(session)
    snapshots = await scorecard_repository.list_scorecard_snapshots(session, period)
    snapshot_values = {
        f"{snapshot.year}-{snapshot.month:02d}": read_snapshot_values(snapshot.raw)
        for snapshot in snapshots
    }
    # SQLAlchemy `Mapped[X]` resolve para `X` em tempo de execução (e para o
    # protocolo estrutural `PublicationLike`), mas o mypy sem o plugin do
    # SQLAlchemy não enxerga essa resolução — mesma classe de aviso já vista
    # em `select_publication_for_period` (app/modules/rdo/router.py e afins).
    return compute_general_panel(publications, period, snapshot_values=snapshot_values)  # type: ignore[arg-type]


@dataclass(slots=True)
class AvailablePeriod:
    period_key: str
    reference_year: int
    semester: str
    month_start: int
    month_end: int
    competencies: list[MonthReference]
    label: str


async def list_available_periods(session: AsyncSession) -> list[AvailablePeriod]:
    """Deriva os ciclos operacionais (Ano+Semestre) que têm ao menos uma
    competência publicada em algum dos 5 módulos de origem — contrato
    explícito `periodKey`/`referenceYear`/`semester`/mês inicial/mês final/
    lista exata de competências, adicional ao `PeriodRange` já usado."""
    publications = await scorecard_repository.list_all_source_publications(session)

    months: set[tuple[int, int]] = set()
    for indicator in SC_INDICATORS:
        if indicator.source is None:
            continue
        matching = [
            p
            for p in publications
            if p.module == indicator.source.module and p.indicator == indicator.source.indicator
        ]
        for publication in matching:
            adapted = adapt_publication(indicator.key, publication)  # type: ignore[arg-type]
            for key in adapted.monthly:
                year_text, _, month_text = key.partition("-")
                try:
                    months.add((int(year_text), int(month_text)))
                except ValueError:
                    continue

    month_refs = [MonthReference(year=y, month=m) for y, m in months]
    cycles = available_cycles_from_months(month_refs)

    results: list[AvailablePeriod] = []
    for cycle in cycles:
        resolved = year_semester_from_cycle(cycle)
        competencies = sorted(
            (MonthReference(year=y, month=m) for y, m in months if _in_cycle(y, m, cycle)),
            key=lambda c: (c.year, c.month),
        )
        results.append(
            AvailablePeriod(
                period_key=f"{resolved.period_year}.{resolved.semester.value}",
                reference_year=resolved.period_year,
                semester=resolved.semester.value,
                month_start=cycle.start_month,
                month_end=cycle.end_month,
                competencies=competencies,
                label=format_period_option_label(resolved.period_year, resolved.semester),
            )
        )
    return results


def _in_cycle(year: int, month: int, cycle: PeriodRange) -> bool:
    return is_within_period_range(year, month, cycle)
