"""Rotas da Taxa de Acidentes — `/taxa-acidentes`, `/taxa-acidentes/registros`,
`/publicacoes/taxa-acidentes`.

Módulo 100% administrativo/manual (sem motor de importação) — não chama
`register_module`. Porte de `src/app/api/taxa-acidentes/route.ts`,
`src/app/api/taxa-acidentes/registros/route.ts` e
`src/app/api/publicacoes/taxa-acidentes/route.ts`.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.errors import DomainError, NotFoundError
from app.core.permissions import Permission
from app.models.indicators import IndicatorPublication
from app.modules.taxa_acidentes import publications as pub
from app.modules.taxa_acidentes import service
from app.modules.taxa_acidentes.schemas import (
    AccidentEntryIn,
    AccidentRateResultOut,
    DeleteRegistrosIn,
    DeleteResultOut,
    ExcludedUnitsIn,
    ExcludedUnitsOut,
    GetPublicationOut,
    GetTaxaAcidentesOut,
    MonthlyEntryIn,
    MonthlyResultOut,
    MonthlySavedEnvelope,
    MonthlySavedOut,
    PeriodRangeOut,
    PublicationOut,
    PublishedByOut,
    PublishIn,
    PublishOut,
    RegistrosCountOut,
    SettingsEntryIn,
    SettingsSavedEnvelope,
    SettingsSavedOut,
    UnitEntryIn,
    UnitResultOut,
    UnitSavedEnvelope,
    UnitSavedOut,
)
from app.modules.taxa_acidentes.types import AccidentRateResult
from app.shared.audit import record_audit
from app.shared.period import PeriodRange, normalize_period_range
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


def _result_out(result: AccidentRateResult) -> AccidentRateResultOut:
    return AccidentRateResultOut(
        target=result.target,
        excluded_units=result.excluded_units,
        period=PeriodRangeOut(
            start_year=result.period.start_year, start_month=result.period.start_month,
            end_year=result.period.end_year, end_month=result.period.end_month,
        )
        if result.period
        else None,
        result=result.result,
        total_caf=result.total_caf,
        total_unit_caf=result.total_unit_caf,
        total_saf=result.total_saf,
        latest_rate=result.latest_rate,
        latest_year=result.latest_year,
        latest_month=result.latest_month,
        months_count=result.months_count,
        monthly=[
            MonthlyResultOut(
                id=m.id or "", year=m.year, month=m.month, rate=m.rate, caf=m.caf,
                label=m.label, ok=m.ok,
            )
            for m in result.monthly
        ],
        units=[
            UnitResultOut(
                id=u.id or "", year=u.year, month=u.month, unit=u.unit, unit_key=u.unit_key,
                saf=u.saf, caf=u.caf, label=u.label, excluded=u.excluded,
            )
            for u in result.units
        ],
    )


@router.get("/taxa-acidentes", response_model=GetTaxaAcidentesOut)
async def get_taxa_acidentes(
    period: Annotated[PeriodRange | None, Depends(period_range_query)] = None,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_READ)),
) -> GetTaxaAcidentesOut:
    data = await service.load_accident_rate_data(session, period)
    return GetTaxaAcidentesOut(
        monthly=[
            {"id": m.id or "", "year": m.year, "month": m.month, "rate": m.rate, "caf": m.caf}
            for m in data.monthly
        ],
        units=[
            {
                "id": u.id or "", "year": u.year, "month": u.month, "unit": u.unit,
                "unitKey": u.unit_key, "saf": u.saf, "caf": u.caf,
            }
            for u in data.units
        ],
        target=data.target,
        excluded_units=data.excluded_units,
        result=_result_out(data.result),
    )


@router.post("/taxa-acidentes")
async def post_taxa_acidentes(
    body: AccidentEntryIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.IMPORT_RUN)),
) -> MonthlySavedEnvelope | UnitSavedEnvelope | SettingsSavedEnvelope:
    if isinstance(body, MonthlyEntryIn):
        monthly_outcome = await service.upsert_monthly_entry(
            session, id=body.id, year=body.year, month=body.month, rate=body.rate, caf=body.caf
        )
        await record_audit(
            session,
            user_id=current_user.id,
            action="RECORD_CREATED" if monthly_outcome.created else "RECORD_EDITED",
            entity="AccidentMonthlyRecord",
            entity_id=monthly_outcome.saved.id,
            previous_data=monthly_outcome.previous,
            new_data={
                "year": monthly_outcome.saved.year, "month": monthly_outcome.saved.month,
                "rate": monthly_outcome.saved.rate, "caf": monthly_outcome.saved.caf,
            },
            metadata={"module": "taxa-acidentes"},
        )
        await session.commit()
        return MonthlySavedEnvelope(
            saved=MonthlySavedOut(
                id=monthly_outcome.saved.id, year=monthly_outcome.saved.year,
                month=monthly_outcome.saved.month, rate=monthly_outcome.saved.rate,
                caf=monthly_outcome.saved.caf,
            )
        )

    if isinstance(body, UnitEntryIn):
        unit_outcome = await service.upsert_unit_entry(
            session, id=body.id, year=body.year, month=body.month,
            unit=body.unit, saf=body.saf, caf=body.caf,
        )
        await record_audit(
            session,
            user_id=current_user.id,
            action="RECORD_CREATED" if unit_outcome.created else "RECORD_EDITED",
            entity="AccidentUnitRecord",
            entity_id=unit_outcome.saved.id,
            previous_data=unit_outcome.previous,
            new_data={
                "year": unit_outcome.saved.year, "month": unit_outcome.saved.month,
                "unit": unit_outcome.saved.unit,
                "saf": unit_outcome.saved.saf, "caf": unit_outcome.saved.caf,
            },
            metadata={"module": "taxa-acidentes"},
        )
        await session.commit()
        return UnitSavedEnvelope(
            saved=UnitSavedOut(
                id=unit_outcome.saved.id, year=unit_outcome.saved.year, month=unit_outcome.saved.month,
                unit=unit_outcome.saved.unit, unit_key=unit_outcome.saved.unitKey,
                saf=unit_outcome.saved.saf, caf=unit_outcome.saved.caf,
            )
        )

    body_settings: SettingsEntryIn = body
    await service.save_accident_target(session, body_settings.target)
    await record_audit(
        session,
        user_id=current_user.id,
        action="INDICATOR_SETTINGS_UPDATED",
        entity="AppSetting",
        entity_id="taxa-acidentes",
        new_data={"target": body_settings.target},
        metadata={"module": "taxa-acidentes"},
    )
    await session.commit()
    return SettingsSavedEnvelope(saved=SettingsSavedOut(target=body_settings.target))


@router.patch("/taxa-acidentes", response_model=ExcludedUnitsOut)
async def patch_taxa_acidentes_settings(
    body: ExcludedUnitsIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.IMPORT_RUN)),
) -> ExcludedUnitsOut:
    excluded_units = await service.save_accident_excluded_units(session, list(body.excluded_units))
    await record_audit(
        session,
        user_id=current_user.id,
        action="INDICATOR_SETTINGS_UPDATED",
        entity="AppSetting",
        entity_id="taxa-acidentes",
        new_data={"excludedUnits": excluded_units},
        metadata={"module": "taxa-acidentes"},
    )
    await session.commit()
    return ExcludedUnitsOut(ok=True, excluded_units=excluded_units)


@router.delete("/taxa-acidentes", response_model=DeleteResultOut)
async def delete_taxa_acidentes_single(
    kind: Literal["month", "unit"] = Query(...),
    year: int | None = Query(default=None),
    month: int | None = Query(default=None),
    id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.IMPORT_RUN)),
) -> DeleteResultOut:
    if kind == "month":
        if year is None or month is None:
            raise DomainError("Informe year e month para excluir um lançamento mensal.")
        deleted = await service.delete_monthly_entry(session, year=year, month=month)
        if deleted is None:
            return DeleteResultOut(ok=True, deleted=0)
        await record_audit(
            session, user_id=current_user.id, action="RECORD_DELETED", entity="AccidentMonthlyRecord",
            entity_id=deleted.id,
            previous_data={
                "year": deleted.year, "month": deleted.month, "rate": deleted.rate, "caf": deleted.caf,
            },
            metadata={"module": "taxa-acidentes"},
        )
        await session.commit()
        return DeleteResultOut(ok=True, deleted=1)

    if id is None:
        raise DomainError("Informe id para excluir um lançamento por unidade.")
    deleted_unit = await service.delete_unit_entry(session, record_id=id)
    if deleted_unit is None:
        raise NotFoundError("Lançamento não encontrado.")
    await record_audit(
        session, user_id=current_user.id, action="RECORD_DELETED", entity="AccidentUnitRecord",
        entity_id=deleted_unit.id,
        previous_data={
            "year": deleted_unit.year, "month": deleted_unit.month, "unit": deleted_unit.unit,
            "saf": deleted_unit.saf, "caf": deleted_unit.caf,
        },
        metadata={"module": "taxa-acidentes"},
    )
    await session.commit()
    return DeleteResultOut(ok=True, deleted=1)


@router.get("/taxa-acidentes/registros", response_model=RegistrosCountOut)
async def get_taxa_acidentes_registros_count(
    period: Annotated[PeriodRange | None, Depends(period_range_query)] = None,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_EDIT)),
) -> RegistrosCountOut:
    counts = await service.count_records(session, period)
    return RegistrosCountOut(count=counts.total)


@router.delete("/taxa-acidentes/registros", response_model=DeleteResultOut)
async def delete_taxa_acidentes_registros(
    body: DeleteRegistrosIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_EDIT)),
) -> DeleteResultOut:
    if body.all is True:
        counts = await service.clear_all_records(session)
        if counts.total == 0:
            return DeleteResultOut(ok=True, deleted=0)
        await record_audit(
            session, user_id=current_user.id, action="RECORDS_CLEARED", entity="AccidentMonthlyRecord",
            previous_data={"quantidade": counts.total},
            metadata={"module": "taxa-acidentes", "escopo": "todos"},
        )
        await session.commit()
        return DeleteResultOut(ok=True, deleted=counts.total)

    range_ = _period_from_fields(
        body.period_start_year, body.period_start_month, body.period_end_year, body.period_end_month
    )
    if range_ is None:
        raise DomainError("Período incompleto.")

    counts = await service.clear_records_in_period(session, range_)
    if counts.total == 0:
        return DeleteResultOut(ok=True, deleted=0)
    await record_audit(
        session, user_id=current_user.id, action="RECORDS_CLEARED", entity="AccidentMonthlyRecord",
        previous_data={"quantidade": counts.total},
        metadata={"module": "taxa-acidentes", "escopo": "periodo"},
    )
    await session.commit()
    return DeleteResultOut(ok=True, deleted=counts.total)


def _publication_out(publication: IndicatorPublication) -> PublicationOut:
    return PublicationOut(
        id=publication.id, module=publication.module, indicator=publication.indicator,
        version=publication.version, target=publication.target, result=publication.result,
        status=publication.status, payload=publication.payload, active=publication.active,
        published_by_id=publication.publishedById, published_at=publication.publishedAt.isoformat(),
        cycle_year=publication.cycleYear, cycle_semester=publication.cycleSemester,
        period_start_year=publication.periodStartYear, period_start_month=publication.periodStartMonth,
        period_end_year=publication.periodEndYear, period_end_month=publication.periodEndMonth,
        published_by=PublishedByOut(
            id=publication.publishedBy.id, name=publication.publishedBy.name,
            email=publication.publishedBy.email,
        ),
    )


@router.get("/publicacoes/taxa-acidentes", response_model=GetPublicationOut)
async def get_publicacoes_taxa_acidentes(
    period: Annotated[PeriodRange | None, Depends(period_range_query)] = None,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_READ)),
) -> GetPublicationOut:
    all_versions = await pub.list_publications(session)
    publication, history_count = select_publication_for_period(all_versions, period)  # type: ignore[type-var]
    return GetPublicationOut(
        publication=_publication_out(publication) if publication else None, history_count=history_count
    )


@router.post("/publicacoes/taxa-acidentes", response_model=PublishOut)
async def post_publicacoes_taxa_acidentes(
    body: PublishIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_PUBLISH)),
) -> PublishOut:
    period = _period_from_fields(
        body.period_start_year, body.period_start_month, body.period_end_year, body.period_end_month
    )
    cycle = resolve_publication_cycle(period)

    data = await service.load_accident_rate_data(session, period)
    payload = pub.to_accident_rate_published_payload(data.result)
    status = "OK" if data.result.result is not None and data.result.result <= data.result.target else "ACIMA"

    await service.recalc_accident_rate_indicators(session, data.result)

    publication = await pub.create_publication(
        session, period=period, cycle=cycle, payload=payload, status=status, user_id=current_user.id
    )

    await record_audit(
        session,
        user_id=current_user.id,
        action="INDICATOR_PUBLISHED",
        entity="IndicatorPublication",
        entity_id=publication.id,
        new_data={
            "module": "taxa-acidentes", "indicator": "taxa", "version": publication.version,
            "target": data.result.target, "result": data.result.result, "status": status,
        },
    )
    await session.commit()
    return PublishOut(publication=_publication_out(publication))
