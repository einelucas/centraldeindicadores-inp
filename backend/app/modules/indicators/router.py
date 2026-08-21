"""Rota de indicadores consolidados — `/indicadores`. Porte de
`src/app/api/indicadores/route.ts`."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission
from app.modules.indicators import service
from app.modules.indicators.schemas import IndicatorResultListOut, IndicatorResultOut

router = APIRouter()


@router.get("/indicadores", response_model=IndicatorResultListOut)
async def list_indicadores(
    year: int | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_READ)),
) -> IndicatorResultListOut:
    rows = await service.list_indicator_results(session, year=year)
    return IndicatorResultListOut(
        items=[
            IndicatorResultOut(
                id=r.id,
                module=r.module,
                indicator=r.indicator,
                unit=r.unit,
                year=r.year,
                month=r.month,
                value=r.value,
                target=r.target,
                adherence=r.adherence,
                status=r.status,
                details=r.details,
                updated_at=r.updatedAt,
            )
            for r in rows
        ]
    )
