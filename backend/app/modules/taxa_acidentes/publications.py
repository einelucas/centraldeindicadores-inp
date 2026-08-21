"""Publicação da Taxa de Acidentes — payload publicado, versionamento e
seleção por período.

Porte de `src/features/taxa-acidentes/publications/index.ts` (payload) e da
lógica de `src/app/api/publicacoes/taxa-acidentes/route.ts` (versionamento e
seleção). A seleção por período/ciclo reaproveita
`app.shared.publication_cycle` (compartilhado entre módulos) — não
reimplementada aqui.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import DomainError
from app.models.indicators import IndicatorPublication
from app.modules.taxa_acidentes.types import (
    ACCIDENT_RATE_SCORECARD_POINTS,
    ACCIDENT_RATE_SCORECARD_WEIGHT,
    INDICATOR,
    MODULE,
    AccidentRateResult,
)
from app.shared.period import PeriodRange
from app.shared.publication_cycle import PublicationCycle
from app.shared.units import format_unit_label


def to_accident_rate_published_payload(result: AccidentRateResult) -> dict:
    """Porte literal de `toAccidentRatePublishedPayload`. Os nomes de campo em
    português (`pontos, peso, meta, resultado, metaFrequencia, acidentesCaf,
    acidentesCafPorUnidade, acidentesSaf, desempenhoMes, referenceYear,
    referenceMonth, periodo, mensal, unidades`) são literais — o front-end e o
    Painel Geral dependem deles."""
    if (
        result.result is None
        or result.latest_rate is None
        or result.latest_year is None
        or result.latest_month is None
    ):
        raise DomainError("Não há meses válidos para publicar a Taxa de Acidentes.")

    return {
        "pontos": ACCIDENT_RATE_SCORECARD_POINTS,
        "peso": ACCIDENT_RATE_SCORECARD_WEIGHT,
        "meta": result.target,
        "resultado": result.result,
        "metaFrequencia": result.target,
        "acidentesCaf": result.total_caf,
        "acidentesCafPorUnidade": result.total_unit_caf,
        "acidentesSaf": result.total_saf,
        "desempenhoMes": result.latest_rate,
        "referenceYear": result.latest_year,
        "referenceMonth": result.latest_month,
        "periodo": (
            {
                "startYear": result.period.start_year,
                "startMonth": result.period.start_month,
                "endYear": result.period.end_year,
                "endMonth": result.period.end_month,
            }
            if result.period is not None
            else None
        ),
        "mensal": [{"label": month.label, "taxa": month.rate, "caf": month.caf} for month in result.monthly],
        "unidades": [
            {
                "year": unit.year,
                "month": unit.month,
                "label": unit.label,
                "unidade": format_unit_label(unit.unit),
                "caf": unit.caf,
                "saf": unit.saf,
            }
            for unit in result.units
            if not unit.excluded
        ],
    }


async def list_publications(session: AsyncSession) -> list[IndicatorPublication]:
    result = await session.execute(
        select(IndicatorPublication)
        .where(IndicatorPublication.module == MODULE, IndicatorPublication.indicator == INDICATOR)
        .order_by(IndicatorPublication.publishedAt.desc(), IndicatorPublication.version.desc())
        .options(selectinload(IndicatorPublication.publishedBy))
    )
    return list(result.scalars().all())


async def _next_version(session: AsyncSession) -> int:
    result = await session.execute(
        select(IndicatorPublication.version)
        .where(IndicatorPublication.module == MODULE, IndicatorPublication.indicator == INDICATOR)
        .order_by(IndicatorPublication.version.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    return (latest or 0) + 1


async def _deactivate_previous_publications(session: AsyncSession, cycle: PublicationCycle | None) -> None:
    """Desativa publicações ativas anteriores. Se `cycle` resolvido, só as do
    MESMO ciclo; senão (período nulo/"Tudo"/recorte parcial), TODAS as ativas
    do módulo — comportamento intencional, ver inventário/summary."""
    stmt = select(IndicatorPublication).where(
        IndicatorPublication.module == MODULE,
        IndicatorPublication.indicator == INDICATOR,
        IndicatorPublication.active.is_(True),
    )
    if cycle is not None:
        stmt = stmt.where(
            IndicatorPublication.cycleYear == cycle.year,
            IndicatorPublication.cycleSemester == cycle.semester.value,
        )
    result = await session.execute(stmt)
    for publication in result.scalars().all():
        publication.active = False
    await session.flush()


async def create_publication(
    session: AsyncSession,
    *,
    period: PeriodRange | None,
    cycle: PublicationCycle | None,
    payload: dict,
    status: str,
    user_id: str,
) -> IndicatorPublication:
    version = await _next_version(session)
    await _deactivate_previous_publications(session, cycle)

    publication = IndicatorPublication(
        module=MODULE,
        indicator=INDICATOR,
        version=version,
        target=payload["meta"],
        result=payload["resultado"],
        status=status,
        payload=payload,
        active=True,
        publishedById=user_id,
        cycleYear=cycle.year if cycle is not None else None,
        cycleSemester=cycle.semester.value if cycle is not None else None,
        periodStartYear=period.start_year if period is not None else None,
        periodStartMonth=period.start_month if period is not None else None,
        periodEndYear=period.end_year if period is not None else None,
        periodEndMonth=period.end_month if period is not None else None,
    )
    session.add(publication)
    await session.flush()

    reloaded = await session.execute(
        select(IndicatorPublication)
        .where(IndicatorPublication.id == publication.id)
        .options(selectinload(IndicatorPublication.publishedBy))
    )
    return reloaded.scalar_one()
