"""Rotas do Painel Geral — `/dashboard`, `/available-periods`.

Porte de `src/app/api/dashboard/route.ts` e `src/app/api/available-periods/route.ts`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission
from app.modules.dashboard import service
from app.modules.dashboard.schemas import (
    AvailablePeriodOut,
    AvailablePeriodsOut,
    CompetencyOut,
    GeneralPanelIndicatorOut,
    GeneralPanelMonthCellOut,
    GeneralPanelOut,
    PeriodRangeOut,
    PublicationRefOut,
)
from app.shared.period import PeriodRange, year_semester_from_cycle
from app.shared.period_params import period_range_query

router = APIRouter()


@router.get("/dashboard", response_model=GeneralPanelOut)
async def get_dashboard(
    period: Annotated[PeriodRange | None, Depends(period_range_query)] = None,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_READ)),
) -> GeneralPanelOut:
    effective_period = await service.resolve_effective_period(session, period)
    panel = await service.get_general_panel(session, effective_period)

    # Melhor esforço: rotula o período como Ano+Semestre mesmo que o range
    # efetivo não seja um ciclo canônico inteiro (ex.: período customizado
    # via query string) — `year_semester_from_cycle` sempre resolve algo,
    # nunca lança, então o rótulo pode ficar aproximado nesse caso raro.
    resolved = year_semester_from_cycle(effective_period)
    period_key = f"{resolved.period_year}.{resolved.semester.value}"

    return GeneralPanelOut(
        has_data=panel.has_data,
        period=PeriodRangeOut(
            start_year=effective_period.start_year, start_month=effective_period.start_month,
            end_year=effective_period.end_year, end_month=effective_period.end_month,
        ),
        period_key=period_key,
        month_keys=panel.month_keys,
        month_labels=panel.month_labels,
        pontuacao_prevista=panel.pontuacao_prevista,
        pontuacao_prevista_semestre=panel.pontuacao_prevista_semestre,
        pontos_realizados=panel.pontos_realizados,
        atendimento_geral=panel.atendimento_geral,
        percentual_semestre_completo=panel.percentual_semestre_completo,
        percentual_dados_disponiveis=panel.percentual_dados_disponiveis,
        reference_date=panel.reference_date,
        indicators=[
            GeneralPanelIndicatorOut(
                key=i.key, label=i.label, short_label=i.short_label, peso=i.peso, meta=i.meta,
                direction=i.direction, unit=i.unit, result=i.result, has_data=i.has_data,
                passed=i.passed, partial=i.partial, partial_pass=i.partial_pass,
                months=[
                    GeneralPanelMonthCellOut(
                        key=m.key, label=m.label, value=m.value, passed=m.passed,
                        pct_of_meta=m.pct_of_meta,
                    )
                    for m in i.months
                ],
                publication=(
                    PublicationRefOut(
                        id=i.publication.id, version=i.publication.version,
                        published_at=i.publication.published_at,
                        published_by_id=i.publication.published_by_id,
                        published_by_name=i.publication.published_by_name,
                        published_by_email=i.publication.published_by_email,
                    )
                    if i.publication
                    else None
                ),
            )
            for i in panel.indicators
        ],
    )


@router.get("/available-periods", response_model=AvailablePeriodsOut)
async def get_available_periods(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_READ)),
) -> AvailablePeriodsOut:
    periods = await service.list_available_periods(session)
    return AvailablePeriodsOut(
        periods=[
            AvailablePeriodOut(
                period_key=p.period_key, reference_year=p.reference_year, semester=p.semester,
                month_start=p.month_start, month_end=p.month_end,
                competencies=[CompetencyOut(year=c.year, month=c.month) for c in p.competencies],
                label=p.label,
            )
            for p in periods
        ]
    )
