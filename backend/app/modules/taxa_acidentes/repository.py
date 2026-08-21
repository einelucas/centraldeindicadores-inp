"""Consultas SQL — `AccidentMonthlyRecord`, `AccidentUnitRecord`, `AppSetting`
e o subconjunto de `IndicatorResult` usado pela publicação deste módulo.

Camada fina: sem regra de negócio (isso vive em `service.py`/`publications.py`).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.indicators import IndicatorResult
from app.models.records import AccidentMonthlyRecord, AccidentUnitRecord
from app.models.settings import AppSetting
from app.shared.period import PeriodRange, period_range_predicate

# --- AccidentMonthlyRecord ---------------------------------------------------


async def list_all_monthly(session: AsyncSession) -> list[AccidentMonthlyRecord]:
    result = await session.execute(
        select(AccidentMonthlyRecord).order_by(AccidentMonthlyRecord.year, AccidentMonthlyRecord.month)
    )
    return list(result.scalars().all())


async def get_monthly_by_id(session: AsyncSession, record_id: str) -> AccidentMonthlyRecord | None:
    return await session.get(AccidentMonthlyRecord, record_id)


async def get_monthly_by_year_month(
    session: AsyncSession, year: int, month: int
) -> AccidentMonthlyRecord | None:
    result = await session.execute(
        select(AccidentMonthlyRecord).where(
            AccidentMonthlyRecord.year == year, AccidentMonthlyRecord.month == month
        )
    )
    return result.scalar_one_or_none()


async def count_monthly(session: AsyncSession, period: PeriodRange | None) -> int:
    stmt = select(func.count()).select_from(AccidentMonthlyRecord)
    if period is not None:
        stmt = stmt.where(
            period_range_predicate(period, AccidentMonthlyRecord.year, AccidentMonthlyRecord.month)
        )
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def delete_all_monthly(session: AsyncSession) -> None:
    await session.execute(delete(AccidentMonthlyRecord))


async def delete_monthly_in_period(session: AsyncSession, period: PeriodRange) -> None:
    await session.execute(
        delete(AccidentMonthlyRecord).where(
            period_range_predicate(period, AccidentMonthlyRecord.year, AccidentMonthlyRecord.month)
        )
    )


# --- AccidentUnitRecord -------------------------------------------------------


async def list_all_units(session: AsyncSession) -> list[AccidentUnitRecord]:
    result = await session.execute(
        select(AccidentUnitRecord).order_by(
            AccidentUnitRecord.year, AccidentUnitRecord.month, AccidentUnitRecord.unit
        )
    )
    return list(result.scalars().all())


async def get_unit_by_id(session: AsyncSession, record_id: str) -> AccidentUnitRecord | None:
    return await session.get(AccidentUnitRecord, record_id)


async def list_units_for_period(session: AsyncSession, year: int, month: int) -> list[AccidentUnitRecord]:
    result = await session.execute(
        select(AccidentUnitRecord).where(AccidentUnitRecord.year == year, AccidentUnitRecord.month == month)
    )
    return list(result.scalars().all())


async def count_units(session: AsyncSession, period: PeriodRange | None) -> int:
    stmt = select(func.count()).select_from(AccidentUnitRecord)
    if period is not None:
        stmt = stmt.where(period_range_predicate(period, AccidentUnitRecord.year, AccidentUnitRecord.month))
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def delete_all_units(session: AsyncSession) -> None:
    await session.execute(delete(AccidentUnitRecord))


async def delete_units_in_period(session: AsyncSession, period: PeriodRange) -> None:
    await session.execute(
        delete(AccidentUnitRecord).where(
            period_range_predicate(period, AccidentUnitRecord.year, AccidentUnitRecord.month)
        )
    )


# --- AppSetting ----------------------------------------------------------------


async def get_setting(session: AsyncSession, key: str) -> AppSetting | None:
    return await session.get(AppSetting, key)


async def upsert_setting(session: AsyncSession, key: str, value: Any) -> None:
    setting = await session.get(AppSetting, key)
    if setting is None:
        session.add(AppSetting(key=key, value=value))
    else:
        setting.value = value
    await session.flush()


# --- IndicatorResult (só o subconjunto do módulo) -------------------------------


async def get_indicator_result(
    session: AsyncSession, *, module: str, indicator: str, unit: str, year: int, month: int
) -> IndicatorResult | None:
    result = await session.execute(
        select(IndicatorResult).where(
            IndicatorResult.module == module,
            IndicatorResult.indicator == indicator,
            IndicatorResult.unit == unit,
            IndicatorResult.year == year,
            IndicatorResult.month == month,
        )
    )
    return result.scalar_one_or_none()


async def delete_indicator_results_for_module(session: AsyncSession, module: str) -> None:
    await session.execute(delete(IndicatorResult).where(IndicatorResult.module == module))
