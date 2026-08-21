"""Rotas do módulo 5S — `/cinco-s`, `/cinco-s/registros`, `/publicacoes/cinco-s`.

Porte de `src/app/api/cinco-s/route.ts`, `src/app/api/cinco-s/registros/route.ts`
e `src/app/api/publicacoes/cinco-s/route.ts`. Registra o módulo no motor de
importação genérico na importação deste arquivo.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.errors import DomainError
from app.core.permissions import Permission
from app.models.indicators import IndicatorPublication
from app.modules.cinco_s.calculations import compute_five_s_result
from app.modules.cinco_s.publications import (
    FiveSPublicationError,
    five_s_published_payload_to_json,
    to_five_s_published_payload,
)
from app.modules.cinco_s.repository import (
    FiveSDelegate,
    count_five_s_records,
    deactivate_publications,
    delete_all_five_s_records,
    delete_all_indicator_results,
    delete_five_s_records_in_period,
    get_last_import,
    get_latest_publication_version,
    list_five_s_records,
    load_five_s_configuration,
    normalize_excluded_units,
    record_from_row,
    save_five_s_settings,
)
from app.modules.cinco_s.schemas import (
    DeleteRegistrosIn,
    DeleteRegistrosOut,
    FiveSAreaOut,
    FiveSGetOut,
    FiveSMonthResultOut,
    FiveSResultOut,
    FiveSUnitMonthOut,
    LastImportOut,
    PeriodRangeOut,
    PublicationGetOut,
    PublicationOut,
    PublishedByOut,
    PublishIn,
    PublishOut,
    RegistrosCountOut,
    SettingsPatchIn,
    SettingsPatchOut,
)
from app.modules.cinco_s.service import recalc_five_s_indicators, to_incremental_records
from app.modules.cinco_s.types import INDICATOR_NAME, MODULE_NAME, FiveSResult
from app.modules.imports.registry import ModuleDefinition, register_module
from app.shared.audit import record_audit
from app.shared.period import PeriodRange, format_period_range_label, normalize_period_range
from app.shared.period_params import period_range_query
from app.shared.publication_cycle import resolve_publication_cycle, select_publication_for_period

router = APIRouter()


def _period_from_fields(
    start_year: int | None, start_month: int | None, end_year: int | None, end_month: int | None
) -> PeriodRange | None:
    if start_year is None or start_month is None or end_year is None or end_month is None:
        return None
    return normalize_period_range(
        PeriodRange(start_year=start_year, start_month=start_month, end_year=end_year, end_month=end_month)
    )


def _result_out(result: FiveSResult) -> FiveSResultOut:
    return FiveSResultOut(
        threshold=result.threshold,
        excluded_units=result.excluded_units,
        period=PeriodRangeOut(
            start_year=result.period.start_year, start_month=result.period.start_month,
            end_year=result.period.end_year, end_month=result.period.end_month,
        )
        if result.period
        else None,
        period_label=result.period_label,
        latest_year=result.latest_year,
        latest_month=result.latest_month,
        geral=result.geral,
        passa_meta=result.passa_meta,
        unit_months=[
            FiveSUnitMonthOut(
                unit=u.unit, year=u.year, month=u.month, aderencia=u.aderencia, excluded=u.excluded,
                areas=[
                    FiveSAreaOut(divisao=a.divisao, area=a.area, meta=a.meta, nota=a.nota)
                    for a in u.areas
                ],
            )
            for u in result.unit_months
        ],
        months=[
            FiveSMonthResultOut(
                year=m.year, month=m.month, label=m.label, geral=m.geral, units_count=m.units_count
            )
            for m in result.months
        ],
        units_count=result.units_count,
        months_count=result.months_count,
    )


@router.get("/cinco-s", response_model=FiveSGetOut)
async def get_cinco_s(
    period: Annotated[PeriodRange | None, Depends(period_range_query)] = None,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_READ)),
) -> FiveSGetOut:
    rows = await list_five_s_records(session)
    threshold, excluded_units = await load_five_s_configuration(session)
    last_import = await get_last_import(session)

    records = [record_from_row(row) for row in rows]
    result = compute_five_s_result(records, excluded_units, threshold, period)

    return FiveSGetOut(
        total=len(rows),
        threshold=threshold,
        excluded_units=excluded_units,
        result=_result_out(result),
        last_import=LastImportOut(
            id=last_import.id, file_name=last_import.fileName, completed_at=last_import.completedAt,
            total_found=last_import.totalFound, total_inserted=last_import.totalInserted,
            total_updated=last_import.totalUpdated, total_ignored=last_import.totalIgnored,
            total_rejected=last_import.totalRejected,
        )
        if last_import
        else None,
    )


@router.patch("/cinco-s", response_model=SettingsPatchOut)
async def patch_cinco_s_settings(
    body: SettingsPatchIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.IMPORT_RUN)),
) -> SettingsPatchOut:
    threshold = body.target / 100
    excluded_units = normalize_excluded_units(list(body.excluded_units))

    await save_five_s_settings(session, threshold=threshold, excluded_units=excluded_units)
    await recalc_five_s_indicators(session)

    await record_audit(
        session,
        user_id=current_user.id,
        action="INDICATOR_SETTINGS_UPDATED",
        entity="AppSetting",
        entity_id="cinco-s",
        new_data={"target": threshold, "excludedUnits": excluded_units},
        metadata={"module": "cinco-s"},
    )
    await session.commit()
    return SettingsPatchOut(threshold=threshold, excluded_units=excluded_units)


@router.get("/cinco-s/registros", response_model=RegistrosCountOut)
async def get_cinco_s_registros_count(
    period: Annotated[PeriodRange | None, Depends(period_range_query)] = None,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_EDIT)),
) -> RegistrosCountOut:
    count = await count_five_s_records(session, period)
    return RegistrosCountOut(count=count)


@router.delete("/cinco-s/registros", response_model=DeleteRegistrosOut)
async def delete_cinco_s_registros(
    body: DeleteRegistrosIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_EDIT)),
) -> DeleteRegistrosOut:
    if body.all_records is True:
        count = await count_five_s_records(session, None)
        if count == 0:
            return DeleteRegistrosOut(deleted=0)

        await delete_all_five_s_records(session)
        await delete_all_indicator_results(session)
        await record_audit(
            session,
            user_id=current_user.id,
            action="RECORDS_CLEARED",
            entity="FiveSRecord",
            previous_data={"quantidade": count},
            metadata={"module": "cinco-s", "escopo": "todos"},
        )
        await session.commit()
        return DeleteRegistrosOut(deleted=count)

    range_ = _period_from_fields(
        body.period_start_year, body.period_start_month, body.period_end_year, body.period_end_month
    )
    if range_ is None:
        raise DomainError("Período incompleto.")

    count = await count_five_s_records(session, range_)
    if count == 0:
        return DeleteRegistrosOut(deleted=0)

    await delete_five_s_records_in_period(session, range_)
    await recalc_five_s_indicators(session)
    await record_audit(
        session,
        user_id=current_user.id,
        action="RECORDS_CLEARED",
        entity="FiveSRecord",
        previous_data={"quantidade": count},
        metadata={"module": "cinco-s", "escopo": "periodo", "periodo": format_period_range_label(range_)},
    )
    await session.commit()
    return DeleteRegistrosOut(deleted=count)


def _publication_out(pub: IndicatorPublication) -> PublicationOut:
    return PublicationOut(
        id=pub.id, version=pub.version, target=pub.target, result=pub.result, status=pub.status,
        payload=pub.payload, active=pub.active, published_at=pub.publishedAt,
        cycle_year=pub.cycleYear, cycle_semester=pub.cycleSemester,
        period_start_year=pub.periodStartYear, period_start_month=pub.periodStartMonth,
        period_end_year=pub.periodEndYear, period_end_month=pub.periodEndMonth,
        published_by=PublishedByOut(
            id=pub.publishedBy.id, name=pub.publishedBy.name, email=pub.publishedBy.email
        ),
    )


@router.get("/publicacoes/cinco-s", response_model=PublicationGetOut)
async def get_publicacoes_cinco_s(
    period: Annotated[PeriodRange | None, Depends(period_range_query)] = None,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_READ)),
) -> PublicationGetOut:
    result = await session.execute(
        select(IndicatorPublication)
        .where(IndicatorPublication.module == MODULE_NAME, IndicatorPublication.indicator == INDICATOR_NAME)
        .order_by(IndicatorPublication.publishedAt.desc(), IndicatorPublication.version.desc())
        .options(selectinload(IndicatorPublication.publishedBy))
    )
    all_versions = list(result.scalars().all())
    publication, history_count = select_publication_for_period(all_versions, period)  # type: ignore[type-var]

    return PublicationGetOut(
        publication=_publication_out(publication) if publication else None, history_count=history_count
    )


@router.post("/publicacoes/cinco-s", response_model=PublishOut)
async def post_publicacoes_cinco_s(
    body: PublishIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_PUBLISH)),
) -> PublishOut:
    rows = await list_five_s_records(session)
    if not rows:
        raise DomainError("Não há registros de 5S para publicar.")

    threshold = body.target / 100
    excluded_units = normalize_excluded_units(list(body.excluded_units))
    period = _period_from_fields(
        body.period_start_year, body.period_start_month, body.period_end_year, body.period_end_month
    )
    cycle = resolve_publication_cycle(period)

    records = [record_from_row(row) for row in rows]
    result = compute_five_s_result(records, excluded_units, threshold, period)

    try:
        published = to_five_s_published_payload(result)
    except FiveSPublicationError as exc:
        raise DomainError(str(exc)) from exc

    payload = five_s_published_payload_to_json(published)
    status = "OK" if published.resultado >= published.meta else "ABAIXO"

    await save_five_s_settings(session, threshold=threshold, excluded_units=excluded_units)

    latest_version = await get_latest_publication_version(session)
    version = (latest_version or 0) + 1

    await deactivate_publications(session, cycle=cycle)

    publication = IndicatorPublication(
        module=MODULE_NAME, indicator=INDICATOR_NAME, version=version,
        target=threshold, result=published.resultado / 100, status=status, payload=payload, active=True,
        publishedById=current_user.id,
        cycleYear=cycle.year if cycle else None,
        cycleSemester=cycle.semester.value if cycle else None,
        periodStartYear=period.start_year if period else None,
        periodStartMonth=period.start_month if period else None,
        periodEndYear=period.end_year if period else None,
        periodEndMonth=period.end_month if period else None,
    )
    session.add(publication)
    await session.flush()
    await session.refresh(publication, attribute_names=["publishedBy"])

    await record_audit(
        session,
        user_id=current_user.id,
        action="INDICATOR_PUBLISHED",
        entity="IndicatorPublication",
        entity_id=publication.id,
        new_data={
            "module": MODULE_NAME, "indicator": INDICATOR_NAME, "version": version,
            "target": body.target, "result": published.resultado, "status": status,
        },
    )
    await session.commit()

    return PublishOut(publication=_publication_out(publication))


register_module(
    "cinco-s",
    ModuleDefinition(
        to_incremental_records=to_incremental_records,
        delegate_factory=FiveSDelegate,
        recalc_indicators=recalc_five_s_indicators,
    ),
)
