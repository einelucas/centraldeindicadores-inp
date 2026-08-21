"""Rotas do módulo RDO — `/rdo`, `/rdo/registros`, `/publicacoes/rdo`.

Porte de `src/app/api/rdo/route.ts`, `src/app/api/rdo/registros/route.ts` e
`src/app/api/publicacoes/rdo/route.ts`. Registra o módulo no motor de
importação genérico (`app/modules/imports/registry.py`) na importação deste
arquivo — ver `register_module` ao final.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.errors import DomainError, NotFoundError
from app.core.permissions import Permission
from app.models.common import utcnow
from app.models.indicators import IndicatorPublication, IndicatorResult
from app.models.records import RdoRecord
from app.modules.imports.registry import ModuleDefinition, register_module
from app.modules.rdo.calculations import compute_rdo_result
from app.modules.rdo.publications import to_rdo_published_payload
from app.modules.rdo.repository import (
    RdoDelegate,
    count_records,
    load_calculation_rows,
    load_detail_rows,
    load_filter_options,
    load_last_import,
    load_rdo_configuration,
    save_rdo_configuration,
)
from app.modules.rdo.schemas import (
    PeriodRangeOut,
    PublishedByOut,
    RdoDeleteIn,
    RdoDeleteOut,
    RdoDetalheItemOut,
    RdoEditIn,
    RdoEditOut,
    RdoEditUpdatedOut,
    RdoFiltrosOut,
    RdoGetOut,
    RdoLastImportOut,
    RdoMonthAggregateOut,
    RdoPatchSettingsIn,
    RdoPatchSettingsOut,
    RdoPublicationDetailOut,
    RdoPublicationOut,
    RdoPublicationsGetOut,
    RdoPublishIn,
    RdoRecordsCountOut,
    RdoResultOut,
    RdoUnitAggregateOut,
)
from app.modules.rdo.service import normalize_excluded_units, recalc_rdo_indicators, to_incremental_records
from app.modules.rdo.types import (
    RDO_DEFAULT_TARGET,
    RDO_INDICATOR,
    RDO_MODULE,
    RdoNormalizedRecord,
    RdoResult,
)
from app.shared.audit import record_audit
from app.shared.period import (
    PeriodRange,
    format_period_range_label,
    normalize_period_range,
    period_range_predicate,
)
from app.shared.period_params import period_range_query
from app.shared.publication_cycle import resolve_publication_cycle, select_publication_for_period

router = APIRouter()


def _period_from_fields(
    start_year: int | None, start_month: int | None, end_year: int | None, end_month: int | None
) -> PeriodRange | None:
    """Tudo-ou-nada: só monta um `PeriodRange` se os 4 campos vierem
    presentes (equivalente a `periodFromOptionalFields` do TypeScript)."""
    if start_year is None or start_month is None or end_year is None or end_month is None:
        return None
    return normalize_period_range(
        PeriodRange(start_year=start_year, start_month=start_month, end_year=end_year, end_month=end_month)
    )


def _record_to_normalized(r: RdoRecord) -> RdoNormalizedRecord:
    return RdoNormalizedRecord(
        data_referencia=r.dataReferencia,
        empresa_nome=r.empresaNome,
        status_descricao=r.statusDescricao,
        relatorio_id=r.relatorioId,
        grupo=r.grupo,
        disciplina=r.disciplina,
        year=r.year,
        month=r.month,
        raw=r.raw,
    )


def _result_out(result: RdoResult) -> RdoResultOut:
    return RdoResultOut(
        threshold=result.threshold,
        excluded_units=result.excluded_units,
        period=PeriodRangeOut(
            start_year=result.period.start_year,
            start_month=result.period.start_month,
            end_year=result.period.end_year,
            end_month=result.period.end_month,
        )
        if result.period
        else None,
        total_emitidos=result.total_emitidos,
        total_aprovados=result.total_aprovados,
        total_revisar=result.total_revisar,
        total_preenchendo=result.total_preenchendo,
        units=[
            RdoUnitAggregateOut(
                name=u.name, emitidos=u.emitidos, aprovados=u.aprovados,
                aderencia=u.aderencia, excluded=u.excluded,
            )
            for u in result.units
        ],
        unit_avg=result.unit_avg,
        months=[
            RdoMonthAggregateOut(
                year=m.year, month=m.month, label=m.label, emitidos=m.emitidos, aprovados=m.aprovados,
                aderencia=m.aderencia,
            )
            for m in result.months
        ],
    )


@router.get("/rdo", response_model=RdoGetOut)
async def get_rdo(
    unidade: str | None = None,
    status: str | None = None,
    q: str | None = None,
    ano: int | None = None,
    mes: int | None = None,
    threshold: float | None = Query(default=None),
    period: Annotated[PeriodRange | None, Depends(period_range_query)] = None,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_READ)),
) -> RdoGetOut:
    filters = []
    if unidade:
        filters.append(RdoRecord.empresaNome == unidade)
    if status:
        filters.append(RdoRecord.statusDescricao == status)
    if q:
        like = f"%{q}%"
        filters.append(
            or_(
                RdoRecord.empresaNome.ilike(like),
                RdoRecord.disciplina.ilike(like),
                RdoRecord.grupo.ilike(like),
                RdoRecord.relatorioId.ilike(like),
            )
        )
    if ano is not None:
        filters.append(RdoRecord.year == ano)
    if mes is not None:
        filters.append(RdoRecord.month == mes)

    threshold_fraction = RDO_DEFAULT_TARGET
    if threshold is not None:
        raw = threshold / 100
        threshold_fraction = min(1.0, max(0.0, raw))

    calculation_rows = await load_calculation_rows(session, filters)
    detail_rows = await load_detail_rows(session, filters, limit=1000)
    total = await count_records(session, filters)
    filter_options = await load_filter_options(session)
    last_import = await load_last_import(session)
    configuration = await load_rdo_configuration(session)

    records = [_record_to_normalized(r) for r in calculation_rows]
    result = compute_rdo_result(records, threshold_fraction, configuration.excluded_units, period)

    return RdoGetOut(
        total=total,
        threshold=threshold_fraction,
        result=_result_out(result),
        detalhe=[
            RdoDetalheItemOut(
                id=r.id, data=r.dataReferencia, unidade=r.empresaNome, grupo=r.grupo, disciplina=r.disciplina,
                status=r.statusDescricao, relatorio_id=r.relatorioId, edited_manually=r.editedManually,
            )
            for r in detail_rows
        ],
        detalhe_limitado=total > len(detail_rows),
        filtros=RdoFiltrosOut(
            unidades=sorted({row[0] for row in filter_options}),
            anos=sorted({row[1] for row in filter_options}, reverse=True),
            status=sorted({row[2] for row in filter_options}),
        ),
        last_import=RdoLastImportOut(
            id=last_import.id, file_name=last_import.fileName, completed_at=last_import.completedAt,
            total_found=last_import.totalFound, total_inserted=last_import.totalInserted,
            total_updated=last_import.totalUpdated, total_ignored=last_import.totalIgnored,
            total_rejected=last_import.totalRejected,
        )
        if last_import
        else None,
    )


@router.patch("/rdo", response_model=RdoPatchSettingsOut)
async def patch_rdo_settings(
    body: RdoPatchSettingsIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.IMPORT_RUN)),
) -> RdoPatchSettingsOut:
    excluded_units = normalize_excluded_units(list(body.excluded_units))
    await save_rdo_configuration(session, excluded_units)
    await recalc_rdo_indicators(session)
    await record_audit(
        session,
        user_id=current_user.id,
        action="INDICATOR_SETTINGS_UPDATED",
        entity="AppSetting",
        entity_id="rdo",
        new_data={"excludedUnits": excluded_units},
        metadata={"module": "rdo"},
    )
    await session.commit()
    return RdoPatchSettingsOut(ok=True, excluded_units=excluded_units)


@router.get("/rdo/registros", response_model=RdoRecordsCountOut)
async def get_rdo_registros_count(
    period: Annotated[PeriodRange | None, Depends(period_range_query)] = None,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_EDIT)),
) -> RdoRecordsCountOut:
    filters = [period_range_predicate(period, RdoRecord.year, RdoRecord.month)] if period else []
    count = await count_records(session, filters)
    return RdoRecordsCountOut(count=count)


@router.patch("/rdo/registros", response_model=RdoEditOut)
async def patch_rdo_registro(
    body: RdoEditIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_EDIT)),
) -> RdoEditOut:
    existing = await session.get(RdoRecord, body.id)
    if existing is None:
        raise NotFoundError("Registro não encontrado.")

    if existing.statusDescricao == body.status:
        return RdoEditOut(ok=True, unchanged=True)

    previous_status = existing.statusDescricao
    existing.statusDescricao = body.status
    existing.editedManually = True
    existing.editedBy = current_user.id
    existing.editedAt = utcnow()
    await session.flush()

    await recalc_rdo_indicators(session)

    await record_audit(
        session,
        user_id=current_user.id,
        action="RECORD_EDITED",
        entity="RdoRecord",
        entity_id=body.id,
        previous_data={"statusDescricao": previous_status},
        new_data={"statusDescricao": body.status},
        metadata={"module": "rdo", "unidade": existing.empresaNome},
    )
    await session.commit()

    updated = RdoEditUpdatedOut(id=existing.id, status_descricao=existing.statusDescricao)
    return RdoEditOut(ok=True, updated=updated)


@router.delete("/rdo/registros", response_model=RdoDeleteOut)
async def delete_rdo_registros(
    body: RdoDeleteIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_EDIT)),
) -> RdoDeleteOut:
    if body.mode == "all":
        count = await count_records(session, [])
        if count == 0:
            return RdoDeleteOut(ok=True, deleted=0)

        await session.execute(delete(RdoRecord))
        await session.execute(delete(IndicatorResult).where(IndicatorResult.module == RDO_MODULE))
        await record_audit(
            session,
            user_id=current_user.id,
            action="RECORDS_CLEARED",
            entity="RdoRecord",
            previous_data={"quantidade": count},
            metadata={"module": "rdo", "escopo": "todos"},
        )
        await session.commit()
        return RdoDeleteOut(ok=True, deleted=count)

    if body.mode == "period":
        range_ = _period_from_fields(
            body.period_start_year, body.period_start_month, body.period_end_year, body.period_end_month
        )
        if range_ is None:
            # Inalcançável em prática: RdoDeleteIn já valida os 4 campos juntos.
            raise DomainError("Período incompleto.")
        filters = [period_range_predicate(range_, RdoRecord.year, RdoRecord.month)]
        count = await count_records(session, filters)
        if count == 0:
            return RdoDeleteOut(ok=True, deleted=0)

        await session.execute(delete(RdoRecord).where(*filters))
        await recalc_rdo_indicators(session)
        await record_audit(
            session,
            user_id=current_user.id,
            action="RECORDS_CLEARED",
            entity="RdoRecord",
            previous_data={"quantidade": count},
            metadata={"module": "rdo", "escopo": "periodo", "periodo": format_period_range_label(range_)},
        )
        await session.commit()
        return RdoDeleteOut(ok=True, deleted=count)

    # mode == "ids"
    ids = body.ids or []
    to_delete_result = await session.execute(select(RdoRecord).where(RdoRecord.id.in_(ids)))
    to_delete = list(to_delete_result.scalars().all())

    result = cast(CursorResult, await session.execute(delete(RdoRecord).where(RdoRecord.id.in_(ids))))
    await recalc_rdo_indicators(session)

    await record_audit(
        session,
        user_id=current_user.id,
        action="RECORD_DELETED",
        entity="RdoRecord",
        entity_id=",".join(ids),
        previous_data={
            "registros": [
                {
                    "id": r.id,
                    "unidade": r.empresaNome,
                    "status": r.statusDescricao,
                    "data": r.dataReferencia.isoformat(),
                }
                for r in to_delete
            ]
        },
        metadata={"module": "rdo", "quantidade": result.rowcount},
    )
    await session.commit()
    return RdoDeleteOut(ok=True, deleted=result.rowcount or 0)


def _publication_out(pub: IndicatorPublication) -> RdoPublicationDetailOut:
    return RdoPublicationDetailOut(
        id=pub.id, version=pub.version, target=pub.target, result=pub.result, status=pub.status,
        payload=pub.payload, published_at=pub.publishedAt,
        published_by=PublishedByOut(
            id=pub.publishedBy.id, name=pub.publishedBy.name, email=pub.publishedBy.email
        ),
    )


@router.get("/publicacoes/rdo", response_model=RdoPublicationsGetOut)
async def get_publicacoes_rdo(
    period: Annotated[PeriodRange | None, Depends(period_range_query)] = None,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_READ)),
) -> RdoPublicationsGetOut:

    result = await session.execute(
        select(IndicatorPublication)
        .where(IndicatorPublication.module == RDO_MODULE, IndicatorPublication.indicator == RDO_INDICATOR)
        .order_by(IndicatorPublication.publishedAt.desc(), IndicatorPublication.version.desc())
        .options(selectinload(IndicatorPublication.publishedBy))
    )
    all_versions = list(result.scalars().all())
    publication, history_count = select_publication_for_period(all_versions, period)  # type: ignore[type-var]

    return RdoPublicationsGetOut(
        publication=_publication_out(publication) if publication else None,
        history_count=history_count,
    )


@router.post("/publicacoes/rdo", response_model=RdoPublicationOut)
async def post_publicacoes_rdo(
    body: RdoPublishIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_PUBLISH)),
) -> RdoPublicationOut:

    threshold_fraction = body.threshold / 100

    rows = await load_calculation_rows(session, [])
    if not rows:
        raise DomainError("Não há registros de RDO para publicar.")

    configuration = await load_rdo_configuration(session)

    period = _period_from_fields(
        body.period_start_year, body.period_start_month, body.period_end_year, body.period_end_month
    )
    cycle = resolve_publication_cycle(period)

    records = [_record_to_normalized(r) for r in rows]
    result = compute_rdo_result(records, threshold_fraction, configuration.excluded_units, period)
    if result.total_emitidos <= 0:
        raise DomainError("Não há RDO emitido para calcular e publicar a aprovação.")

    payload = to_rdo_published_payload(result, body.threshold)
    status = "OK" if payload["resultado"] >= body.threshold else "ABAIXO"

    latest_result = await session.execute(
        select(IndicatorPublication.version)
        .where(IndicatorPublication.module == RDO_MODULE, IndicatorPublication.indicator == RDO_INDICATOR)
        .order_by(IndicatorPublication.version.desc())
        .limit(1)
    )
    latest_version = latest_result.scalar_one_or_none()
    version = (latest_version or 0) + 1

    deactivate_filters = [
        IndicatorPublication.module == RDO_MODULE,
        IndicatorPublication.indicator == RDO_INDICATOR,
        IndicatorPublication.active == True,  # noqa: E712
    ]
    if cycle:
        deactivate_filters.append(IndicatorPublication.cycleYear == cycle.year)
        deactivate_filters.append(IndicatorPublication.cycleSemester == cycle.semester.value)
    await session.execute(update(IndicatorPublication).where(*deactivate_filters).values(active=False))

    publication = IndicatorPublication(
        module=RDO_MODULE,
        indicator=RDO_INDICATOR,
        version=version,
        target=threshold_fraction,
        result=payload["resultado"] / 100,
        status=status,
        payload=payload,
        active=True,
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
            "module": RDO_MODULE, "indicator": RDO_INDICATOR, "version": version,
            "target": body.threshold, "result": payload["resultado"], "status": status,
        },
        metadata={"emitidos": payload["emitidos"], "aprovados": payload["aprovados"]},
    )
    await session.commit()

    return RdoPublicationOut(publication=_publication_out(publication))


register_module(
    "rdo",
    ModuleDefinition(
        to_incremental_records=to_incremental_records,
        delegate_factory=RdoDelegate,
        recalc_indicators=recalc_rdo_indicators,
    ),
)
