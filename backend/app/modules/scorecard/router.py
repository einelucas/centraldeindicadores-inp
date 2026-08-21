"""Rotas do Scorecard — `/scorecard`, `/scorecard/history`, `/scorecard/panel-period`.

Porte de `src/app/api/scorecard/route.ts`, `src/app/api/scorecard/history/route.ts`
e `src/app/api/scorecard/panel-period/route.ts`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.errors import DomainError
from app.core.permissions import Permission
from app.modules.scorecard import service
from app.modules.scorecard.calculations import ScorecardResult
from app.modules.scorecard.schemas import (
    PeriodRangeOut,
    ScorecardComputationOut,
    ScorecardHistoryDeleteOut,
    ScorecardHistoryItemOut,
    ScorecardHistoryOut,
    ScorecardPanelPeriodIn,
    ScorecardPanelPeriodOut,
    ScorecardResultOut,
    ScorecardRowOut,
    ScorecardSaveIn,
)
from app.shared.audit import record_audit
from app.shared.period import PeriodRange, normalize_period_range
from app.shared.period_params import period_range_query

router = APIRouter()


def _result_out(result: ScorecardResult) -> ScorecardResultOut:
    return ScorecardResultOut(
        rows=[
            ScorecardRowOut(
                key=r.key, label=r.label, peso=r.peso, meta=r.meta, direction=r.direction, unit=r.unit,
                value=r.value, **{"pass": r.passed}, pontos=r.pontos,
                pontos_possiveis=r.pontos_possiveis, has_value=r.has_value,
            )
            for r in result.rows
        ],
        total_pontos=result.total_pontos,
        total_peso=result.total_peso,
        pontos_possiveis_mes=result.pontos_possiveis_mes,
        atendimento_mes=result.atendimento_mes,
    )


@router.get("/scorecard", response_model=ScorecardComputationOut)
async def get_scorecard(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_READ)),
) -> ScorecardComputationOut:
    computation = await service.compute_scorecard_for_month(session, year, month)
    return ScorecardComputationOut(
        year=computation.year, month=computation.month, source_values=computation.source_values,
        values=computation.values, result=_result_out(computation.result),
    )


@router.post("/scorecard", response_model=ScorecardComputationOut)
async def post_scorecard(
    body: ScorecardSaveIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_EDIT)),
) -> ScorecardComputationOut:
    computation = await service.save_scorecard_snapshot(
        session, year=body.year, month=body.month, overrides=body.overrides
    )
    await record_audit(
        session,
        user_id=current_user.id,
        action="SCORECARD_SNAPSHOT_SAVED",
        entity="ScorecardSnapshot",
        entity_id=f"{body.year}-{body.month:02d}",
        new_data={"values": computation.values},
        metadata={"module": "scorecard"},
    )
    await session.commit()
    return ScorecardComputationOut(
        year=computation.year, month=computation.month, source_values=computation.source_values,
        values=computation.values, result=_result_out(computation.result),
    )


@router.get("/scorecard/history", response_model=ScorecardHistoryOut)
async def get_scorecard_history(
    period: Annotated[PeriodRange | None, Depends(period_range_query)] = None,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_READ)),
) -> ScorecardHistoryOut:
    items = await service.list_scorecard_history(session, period)
    return ScorecardHistoryOut(
        snapshots=[
            ScorecardHistoryItemOut(
                year=item.year, month=item.month, values=item.values, result=_result_out(item.result)
            )
            for item in items
        ]
    )


@router.delete("/scorecard/history", response_model=ScorecardHistoryDeleteOut)
async def delete_scorecard_history(
    period: Annotated[PeriodRange | None, Depends(period_range_query)] = None,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_EDIT)),
) -> ScorecardHistoryDeleteOut:
    if period is None:
        raise DomainError("Informe o período completo para limpar o histórico do ciclo.")

    deleted = await service.delete_scorecard_history(session, period)
    if deleted:
        await record_audit(
            session,
            user_id=current_user.id,
            action="SCORECARD_HISTORY_CLEARED",
            entity="ScorecardSnapshot",
            previous_data={"quantidade": deleted},
            metadata={"module": "scorecard"},
        )
        await session.commit()
    return ScorecardHistoryDeleteOut(ok=True, deleted=deleted)


@router.get("/scorecard/panel-period", response_model=ScorecardPanelPeriodOut)
async def get_scorecard_panel_period(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_READ)),
) -> ScorecardPanelPeriodOut:
    period = await service.get_panel_period(session)
    return ScorecardPanelPeriodOut(
        period=PeriodRangeOut(
            start_year=period.start_year, start_month=period.start_month,
            end_year=period.end_year, end_month=period.end_month,
        )
        if period
        else None
    )


@router.patch("/scorecard/panel-period", response_model=ScorecardPanelPeriodOut)
async def patch_scorecard_panel_period(
    body: ScorecardPanelPeriodIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_EDIT)),
) -> ScorecardPanelPeriodOut:
    range_ = normalize_period_range(
        PeriodRange(
            start_year=body.start_year, start_month=body.start_month,
            end_year=body.end_year, end_month=body.end_month,
        )
    )
    await service.save_panel_period(session, range_)
    await record_audit(
        session,
        user_id=current_user.id,
        action="SCORECARD_PANEL_PERIOD_UPDATED",
        entity="AppSetting",
        entity_id="scorecard.panelPeriod",
        new_data={
            "startYear": range_.start_year, "startMonth": range_.start_month,
            "endYear": range_.end_year, "endMonth": range_.end_month,
        },
        metadata={"module": "scorecard"},
    )
    await session.commit()
    return ScorecardPanelPeriodOut(
        period=PeriodRangeOut(
            start_year=range_.start_year, start_month=range_.start_month,
            end_year=range_.end_year, end_month=range_.end_month,
        )
    )
