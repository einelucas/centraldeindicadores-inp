"""Acesso a dados do Scorecard/Painel Geral.

Lê `IndicatorPublication` dos 5 módulos de origem (`SC_INDICATORS`),
`ScorecardSnapshot` e a configuração de período de controle
(`AppSetting["scorecard.panelPeriod"]`).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.indicators import IndicatorPublication
from app.models.records import ScorecardSnapshot
from app.models.settings import AppSetting
from app.modules.scorecard.types import SC_INDICATORS, SCORECARD_PANEL_PERIOD_SETTING
from app.shared.hashing import make_business_key, make_content_hash
from app.shared.period import PeriodRange, period_range_predicate

_SOURCE_MODULE_INDICATOR_PAIRS: tuple[tuple[str, str], ...] = tuple(
    (indicator.source.module, indicator.source.indicator)
    for indicator in SC_INDICATORS
    if indicator.source is not None
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def list_all_source_publications(session: AsyncSession) -> list[IndicatorPublication]:
    """Todas as publicações (ativas e históricas) dos 5 módulos de origem do
    Scorecard, com `publishedBy` carregado — usado tanto para o Painel Geral
    quanto para a recuperação de mês em publicação anterior."""
    conditions = [
        (IndicatorPublication.module == module) & (IndicatorPublication.indicator == indicator)
        for module, indicator in _SOURCE_MODULE_INDICATOR_PAIRS
    ]
    if not conditions:
        return []

    result = await session.execute(
        select(IndicatorPublication)
        .where(or_(*conditions))
        .options(selectinload(IndicatorPublication.publishedBy))
        .order_by(IndicatorPublication.publishedAt.desc(), IndicatorPublication.version.desc())
    )
    return list(result.scalars().all())


async def get_scorecard_snapshot(session: AsyncSession, year: int, month: int) -> ScorecardSnapshot | None:
    result = await session.execute(
        select(ScorecardSnapshot).where(ScorecardSnapshot.year == year, ScorecardSnapshot.month == month)
    )
    return result.scalar_one_or_none()


async def list_scorecard_snapshots(
    session: AsyncSession, period: PeriodRange | None
) -> list[ScorecardSnapshot]:
    stmt = select(ScorecardSnapshot).order_by(ScorecardSnapshot.year, ScorecardSnapshot.month)
    if period is not None:
        stmt = stmt.where(period_range_predicate(period, ScorecardSnapshot.year, ScorecardSnapshot.month))
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _scorecard_business_key(year: int, month: int) -> str:
    return make_business_key("SCORECARD", [str(year), str(month)])


async def save_scorecard_snapshot(
    session: AsyncSession, *, year: int, month: int, values: dict[str, float | None]
) -> ScorecardSnapshot:
    """Upsert idempotente por `(year, month)` — cada save gera um `contentHash`
    dos valores para permitir auditoria de mudanças, mas o `businessKey` é
    estável por competência (uma linha por mês, sempre atualizada no lugar)."""
    business_key = _scorecard_business_key(year, month)
    content_hash = make_content_hash({k: v if v is not None else "" for k, v in sorted(values.items())})
    raw = {"values": values}

    existing = await get_scorecard_snapshot(session, year, month)
    marker = str(uuid.uuid4())

    if existing is None:
        snapshot = ScorecardSnapshot(
            businessKey=business_key,
            contentHash=content_hash,
            year=year,
            month=month,
            raw=raw,
            firstImportId=marker,
            lastImportId=marker,
        )
        session.add(snapshot)
    else:
        existing.contentHash = content_hash
        existing.raw = raw
        existing.lastImportId = marker
        existing.lastSeenAt = _utcnow()
        snapshot = existing

    await session.flush()
    return snapshot


async def delete_scorecard_snapshots_in_period(session: AsyncSession, period: PeriodRange) -> int:
    count_stmt = select(ScorecardSnapshot).where(
        period_range_predicate(period, ScorecardSnapshot.year, ScorecardSnapshot.month)
    )
    count_result = await session.execute(count_stmt)
    rows = count_result.scalars().all()
    count = len(rows)
    if count:
        await session.execute(
            delete(ScorecardSnapshot).where(
                period_range_predicate(period, ScorecardSnapshot.year, ScorecardSnapshot.month)
            )
        )
    return count


async def get_panel_period(session: AsyncSession) -> PeriodRange | None:
    setting = await session.get(AppSetting, SCORECARD_PANEL_PERIOD_SETTING)
    if setting is None or not isinstance(setting.value, dict):
        return None
    value = setting.value
    required = ("startYear", "startMonth", "endYear", "endMonth")
    if not all(isinstance(value.get(k), int) for k in required):
        return None
    return PeriodRange(
        start_year=value["startYear"],
        start_month=value["startMonth"],
        end_year=value["endYear"],
        end_month=value["endMonth"],
    )


async def save_panel_period(session: AsyncSession, period: PeriodRange) -> None:
    value = {
        "startYear": period.start_year,
        "startMonth": period.start_month,
        "endYear": period.end_year,
        "endMonth": period.end_month,
    }
    setting = await session.get(AppSetting, SCORECARD_PANEL_PERIOD_SETTING)
    if setting is None:
        session.add(AppSetting(key=SCORECARD_PANEL_PERIOD_SETTING, value=value))
    else:
        setting.value = value
    await session.flush()
