"""Rotas do módulo IDP/RSO — `/idp`, `/idp/registros`, `/publicacoes/idp`.

Porte de `src/app/api/idp/route.ts`, `src/app/api/idp/registros/route.ts` e
`src/app/api/publicacoes/idp/route.ts`. Registra o módulo no motor de
importação genérico (`app/modules/imports/registry.py`) e os hooks de
`idp.excludedDisciplines`/`idp.excludedUnits` em `PATCH /configuracoes`
(`app/modules/settings/hooks.py`) — o IDP não tem uma rota de configuração
própria como RDO/RNC/5S/Taxa; a única forma de alterar essas duas listas é
pela rota genérica de configurações."""

from __future__ import annotations

import math
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.errors import DomainError
from app.core.permissions import Permission
from app.models.imports import ImportJob
from app.models.indicators import IndicatorPublication, IndicatorResult
from app.models.records import IdpRsoRecord
from app.models.settings import AppSetting
from app.models.user import User
from app.modules.idp.calculations import compute_idp_result
from app.modules.idp.publications import to_idp_published_payload
from app.modules.idp.repository import (
    IdpDelegate,
    count_records,
    load_idp_configuration,
    load_last_import,
    reconstruct_records,
)
from app.modules.idp.schemas import (
    IdpDeleteIn,
    IdpDeleteOut,
    IdpDisciplineRowOut,
    IdpDocumentOut,
    IdpExecutionPhaseOut,
    IdpGetOut,
    IdpLastImportOut,
    IdpMonthAggregateOut,
    IdpPublicationDetailOut,
    IdpPublicationOut,
    IdpPublicationsGetOut,
    IdpPublishIn,
    IdpRecordsCountOut,
    IdpResultOut,
    IdpUnitRowOut,
    PublishedByOut,
)
from app.modules.idp.service import recalc_idp_indicators, to_incremental_records
from app.modules.idp.types import (
    IDP_DEFAULT_TARGET,
    IDP_EXCLUDED_DISCIPLINES_SETTING_KEY,
    IDP_EXCLUDED_UNITS_SETTING_KEY,
    IDP_INDICATOR,
    IDP_MODULE,
    IdpNormalizedRecord,
    IdpResult,
)
from app.modules.imports.registry import ModuleDefinition, register_module
from app.modules.settings.hooks import register_setting_hook
from app.shared.audit import record_audit
from app.shared.period import (
    PeriodRange,
    enumerate_period_months,
    format_period_range_label,
    normalize_period_range,
    period_range_predicate,
)
from app.shared.period_params import period_range_query
from app.shared.publication_cycle import resolve_publication_cycle, select_publication_for_period
from app.shared.units import normalize_unit_code

router = APIRouter()


def _period_from_fields(
    start_year: int | None, start_month: int | None, end_year: int | None, end_month: int | None
) -> PeriodRange | None:
    if start_year is None or start_month is None or end_year is None or end_month is None:
        return None
    return normalize_period_range(
        PeriodRange(start_year=start_year, start_month=start_month, end_year=end_year, end_month=end_month)
    )


def _parse_threshold(value: str | None) -> float:
    """`Number.isFinite(thresholdRaw) ? Math.max(0, Math.min(2, thresholdRaw/100))
    : IDP_DEFAULT_TARGET` — clampado entre 0 e 2 (0%-200%) após dividir por 100."""
    if value is None:
        return IDP_DEFAULT_TARGET
    try:
        num = float(value)
    except ValueError:
        return IDP_DEFAULT_TARGET
    if not math.isfinite(num):
        return IDP_DEFAULT_TARGET
    return min(2.0, max(0.0, num / 100))


def _result_out(result: IdpResult) -> IdpResultOut:
    return IdpResultOut(
        threshold=result.threshold,
        excluded_disciplines=result.excluded_disciplines,
        excluded_units=result.excluded_units,
        selected_year=result.selected_year,
        selected_month=result.selected_month,
        history_start_year=result.history_start_year,
        history_month_start=result.history_month_start,
        history_end_year=result.history_end_year,
        history_month_end=result.history_month_end,
        active_documents=result.active_documents,
        aderencia_geral=result.aderencia_geral,
        total_previsto_medio=result.total_previsto_medio,
        total_real_medio=result.total_real_medio,
        unit_rows=[
            IdpUnitRowOut(
                unit=u.unit, rso_numero=u.rso_numero, reference_year=u.reference_year,
                reference_month=u.reference_month, reference_source=u.reference_source,
                reference_original_text=u.reference_original_text, reference_adjusted=u.reference_adjusted,
                period_start=u.period_start, period_end=u.period_end, emission_date=u.emission_date,
                file_name=u.file_name, n_fases=u.n_fases, prev_acum=u.prev_acum, real_acum=u.real_acum,
                aderencia=u.aderencia, excluded=u.excluded,
                phases=[
                    IdpExecutionPhaseOut(label=p.label, prev_acum=p.prev_acum, real_acum=p.real_acum)
                    for p in u.phases
                ],
            )
            for u in result.unit_rows
        ],
        discipline_rows=[
            IdpDisciplineRowOut(
                disciplina=d.disciplina, prev_avg=d.prev_avg, real_avg=d.real_avg, aderencia=d.aderencia
            )
            for d in result.discipline_rows
        ],
        monthly=[
            IdpMonthAggregateOut(
                year=m.year, month=m.month, label=m.label, aderencia=m.aderencia,
                active_documents=m.active_documents, total_previsto_medio=m.total_previsto_medio,
                total_real_medio=m.total_real_medio,
            )
            for m in result.monthly
        ],
    )


def _document_out(
    row: IdpRsoRecord, record: IdpNormalizedRecord, result: IdpResult, importer_names: dict[str, str]
) -> IdpDocumentOut:
    active = any(u.source_id == row.id for u in result.unit_rows)
    same_competence = (
        record.reference_year == result.selected_year and record.reference_month == result.selected_month
    )
    return IdpDocumentOut(
        id=row.id, unit=row.unit, detected_unit=row.detectedUnit, unit_adjusted=row.unitAdjusted,
        rso_numero=row.rsoNumero, detected_rso_numero=row.detectedRsoNumero, rso_adjusted=row.rsoAdjusted,
        reference_year=row.referenceYear, reference_month=row.referenceMonth,
        detected_reference_year=row.detectedReferenceYear,
        detected_reference_month=row.detectedReferenceMonth,
        reference_source=row.referenceSource, reference_original_text=row.referenceOriginalText,
        reference_adjusted=row.referenceAdjusted, period_start=row.periodStart, period_end=row.periodEnd,
        emission_date=row.emissionDate, file_name=row.fileName, areas=len(row.areas or []),
        active=active, same_competence=same_competence, created_at=row.createdAt, updated_at=row.updatedAt,
        first_imported_by=importer_names.get(row.firstImportId),
        last_updated_by=importer_names.get(row.lastImportId),
    )


async def _resolve_importer_names(session: AsyncSession, import_ids: set[str]) -> dict[str, str]:
    if not import_ids:
        return {}
    result = await session.execute(
        select(ImportJob.id, User.name)
        .join(User, User.id == ImportJob.userId)
        .where(ImportJob.id.in_(import_ids))
    )
    return dict(result.tuples().all())


async def _load_all_rows(session: AsyncSession) -> list[IdpRsoRecord]:
    result = await session.execute(
        select(IdpRsoRecord).order_by(
            IdpRsoRecord.referenceYear.desc(), IdpRsoRecord.referenceMonth.desc(),
            IdpRsoRecord.unit.asc(), IdpRsoRecord.rsoNumero.desc(),
        )
    )
    return list(result.scalars().all())


@router.get("/idp", response_model=IdpGetOut)
async def get_idp(
    threshold: str | None = Query(default=None),
    period: Annotated[PeriodRange | None, Depends(period_range_query)] = None,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_READ)),
) -> IdpGetOut:
    threshold_fraction = _parse_threshold(threshold)

    rows = await _load_all_rows(session)
    total = len(rows)
    pairs, invalid = reconstruct_records(rows)
    records = [record for _row, record in pairs]

    configuration = await load_idp_configuration(session)
    last_import = await load_last_import(session)

    result = compute_idp_result(
        records, threshold_fraction, configuration.excluded_disciplines, configuration.excluded_units, period
    )

    years = sorted({r.reference_year for r in records}, reverse=True) or [result.selected_year]

    import_ids = {row.firstImportId for row, _r in pairs} | {row.lastImportId for row, _r in pairs}
    importer_names = await _resolve_importer_names(session, import_ids)
    documents = [_document_out(row, record, result, importer_names) for row, record in pairs]

    return IdpGetOut(
        total=total,
        active_total=result.active_documents,
        threshold=threshold_fraction,
        years=years,
        selected_year=result.selected_year,
        selected_month=result.selected_month,
        history_start_year=result.history_start_year,
        history_month_start=result.history_month_start,
        history_end_year=result.history_end_year,
        history_month_end=result.history_month_end,
        excluded_disciplines=result.excluded_disciplines,
        result=_result_out(result),
        documents=documents,
        last_import=IdpLastImportOut(
            id=last_import.id, file_name=last_import.fileName, completed_at=last_import.completedAt,
            total_found=last_import.totalFound, total_inserted=last_import.totalInserted,
            total_updated=last_import.totalUpdated, total_ignored=last_import.totalIgnored,
            total_rejected=last_import.totalRejected,
        )
        if last_import
        else None,
        invalid_records_skipped=invalid,
    )


@router.get("/idp/registros", response_model=IdpRecordsCountOut)
async def get_idp_registros_count(
    period: Annotated[PeriodRange | None, Depends(period_range_query)] = None,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_EDIT)),
) -> IdpRecordsCountOut:
    filters = (
        [period_range_predicate(period, IdpRsoRecord.referenceYear, IdpRsoRecord.referenceMonth)]
        if period
        else []
    )
    count = await count_records(session, filters)
    return IdpRecordsCountOut(count=count)


@router.delete("/idp/registros", response_model=IdpDeleteOut)
async def delete_idp_registros(
    body: IdpDeleteIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_EDIT)),
) -> IdpDeleteOut:
    """A publicação vigente não é apagada — snapshot histórico imutável. Sem
    modo `ids` (diferente de RDO/RNC): o IDP só permite apagar tudo ou por
    período."""
    if body.mode == "all":
        count = await count_records(session, [])
        if count == 0:
            return IdpDeleteOut(ok=True, deleted=0)

        await session.execute(delete(IdpRsoRecord))
        await session.execute(delete(IndicatorResult).where(IndicatorResult.module == IDP_MODULE))
        await record_audit(
            session, user_id=current_user.id, action="RECORDS_CLEARED", entity="IdpRsoRecord",
            previous_data={"quantidade": count}, metadata={"module": "idp", "escopo": "todos_rsos"},
        )
        await session.commit()
        return IdpDeleteOut(ok=True, deleted=count)

    range_ = _period_from_fields(
        body.period_start_year, body.period_start_month, body.period_end_year, body.period_end_month
    )
    if range_ is None:
        raise DomainError("Período incompleto.")
    filters = [period_range_predicate(range_, IdpRsoRecord.referenceYear, IdpRsoRecord.referenceMonth)]
    count = await count_records(session, filters)
    if count == 0:
        return IdpDeleteOut(ok=True, deleted=0)

    await session.execute(delete(IdpRsoRecord).where(*filters))
    await recalc_idp_indicators(session)
    await record_audit(
        session, user_id=current_user.id, action="RECORDS_CLEARED", entity="IdpRsoRecord",
        previous_data={"quantidade": count},
        metadata={"module": "idp", "escopo": "periodo", "periodo": format_period_range_label(range_)},
    )
    await session.commit()
    return IdpDeleteOut(ok=True, deleted=count)


def _publication_out(pub: IndicatorPublication) -> IdpPublicationDetailOut:
    return IdpPublicationDetailOut(
        id=pub.id, version=pub.version, target=pub.target, result=pub.result, status=pub.status,
        payload=pub.payload, published_at=pub.publishedAt,
        published_by=PublishedByOut(
            id=pub.publishedBy.id, name=pub.publishedBy.name, email=pub.publishedBy.email
        ),
    )


@router.get("/publicacoes/idp", response_model=IdpPublicationsGetOut)
async def get_publicacoes_idp(
    period: Annotated[PeriodRange | None, Depends(period_range_query)] = None,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_READ)),
) -> IdpPublicationsGetOut:
    result = await session.execute(
        select(IndicatorPublication)
        .where(IndicatorPublication.module == IDP_MODULE, IndicatorPublication.indicator == IDP_INDICATOR)
        .order_by(IndicatorPublication.publishedAt.desc(), IndicatorPublication.version.desc())
        .options(selectinload(IndicatorPublication.publishedBy))
    )
    all_versions = list(result.scalars().all())
    publication, history_count = select_publication_for_period(all_versions, period)  # type: ignore[type-var]

    return IdpPublicationsGetOut(
        publication=_publication_out(publication) if publication else None,
        history_count=history_count,
    )


@router.post("/publicacoes/idp", response_model=IdpPublicationOut)
async def post_publicacoes_idp(
    body: IdpPublishIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_PUBLISH)),
) -> IdpPublicationOut:
    period = normalize_period_range(
        PeriodRange(
            start_year=body.period_start_year, start_month=body.period_start_month,
            end_year=body.period_end_year, end_month=body.period_end_month,
        )
    )
    reference_years = sorted({m.year for m in enumerate_period_months(period)})
    cycle = resolve_publication_cycle(period)

    rows_result = await session.execute(
        select(IdpRsoRecord)
        .where(IdpRsoRecord.referenceYear.in_(reference_years))
        .order_by(
            IdpRsoRecord.referenceYear.asc(), IdpRsoRecord.referenceMonth.asc(),
            IdpRsoRecord.unit.asc(), IdpRsoRecord.rsoNumero.asc(),
        )
    )
    rows = list(rows_result.scalars().all())
    if not rows:
        raise DomainError("Não há RSOs no período selecionado para publicar.")

    pairs, _invalid = reconstruct_records(rows)
    records = [record for _row, record in pairs]

    configuration = await load_idp_configuration(session)
    threshold_fraction = body.threshold / 100
    result = compute_idp_result(
        records, threshold_fraction, configuration.excluded_disciplines, configuration.excluded_units, period
    )
    if result.active_documents == 0:
        raise DomainError("Não há RSO no semestre selecionado para publicar.")

    payload = to_idp_published_payload(result, body.threshold)
    status = "OK" if payload["resultado"] >= body.threshold else "ABAIXO"

    latest_result = await session.execute(
        select(IndicatorPublication.version)
        .where(IndicatorPublication.module == IDP_MODULE, IndicatorPublication.indicator == IDP_INDICATOR)
        .order_by(IndicatorPublication.version.desc())
        .limit(1)
    )
    latest_version = latest_result.scalar_one_or_none()
    version = (latest_version or 0) + 1

    deactivate_filters = [
        IndicatorPublication.module == IDP_MODULE,
        IndicatorPublication.indicator == IDP_INDICATOR,
        IndicatorPublication.active == True,  # noqa: E712
    ]
    if cycle:
        deactivate_filters.append(IndicatorPublication.cycleYear == cycle.year)
        deactivate_filters.append(IndicatorPublication.cycleSemester == cycle.semester.value)
    await session.execute(update(IndicatorPublication).where(*deactivate_filters).values(active=False))

    publication = IndicatorPublication(
        module=IDP_MODULE, indicator=IDP_INDICATOR, version=version,
        target=threshold_fraction, result=payload["resultado"] / 100, status=status, payload=payload,
        active=True, publishedById=current_user.id,
        cycleYear=cycle.year if cycle else None, cycleSemester=cycle.semester.value if cycle else None,
        periodStartYear=period.start_year, periodStartMonth=period.start_month,
        periodEndYear=period.end_year, periodEndMonth=period.end_month,
    )
    session.add(publication)
    await session.flush()
    await session.refresh(publication, attribute_names=["publishedBy"])

    await record_audit(
        session, user_id=current_user.id, action="INDICATOR_PUBLISHED", entity="IndicatorPublication",
        entity_id=publication.id,
        new_data={
            "module": IDP_MODULE, "indicator": IDP_INDICATOR, "version": version,
            "year": result.selected_year, "month": result.selected_month,
            "periodStartYear": period.start_year, "periodStartMonth": period.start_month,
            "periodEndYear": period.end_year, "periodEndMonth": period.end_month,
            "target": body.threshold, "result": payload["resultado"], "status": status,
        },
        metadata={
            "documentosAtivos": payload["documentosAtivos"],
            "documentos": [
                {"unidade": u["n"], "rso": u["rsoNumero"], "arquivo": u["fileName"]}
                for u in payload["unidades"]
            ],
        },
    )
    await session.commit()

    return IdpPublicationOut(publication=_publication_out(publication))


_DISCIPLINE_SPLIT_RE = re.compile(r"[\n,]")


async def _handle_excluded_disciplines_setting(session: AsyncSession, setting: AppSetting) -> None:
    """Normaliza `idp.excludedDisciplines`. Aceita tanto uma string
    multi-linha (textarea de admin, um nome por linha ou separado por
    vírgula) quanto um array já pronto — decisão pragmática documentada em
    `docs/backend-migration-decisions.md` §4.2.6, já que o inventário só
    confirmou o comportamento de split de string via teste unitário."""
    raw_value = setting.value
    if isinstance(raw_value, str):
        items: list[Any] = _DISCIPLINE_SPLIT_RE.split(raw_value)
    elif isinstance(raw_value, list):
        items = raw_value
    else:
        items = []
    normalized = [text for v in items if (text := str(v).strip())]
    setting.value = normalized
    await session.flush()
    await recalc_idp_indicators(session)


async def _handle_excluded_units_setting(session: AsyncSession, setting: AppSetting) -> None:
    raw_value = setting.value
    values = raw_value if isinstance(raw_value, list) else []
    seen: list[str] = []
    for v in values:
        code = normalize_unit_code(v)
        if code and code not in seen:
            seen.append(code)
    setting.value = seen
    await session.flush()
    await recalc_idp_indicators(session)


register_setting_hook(IDP_EXCLUDED_DISCIPLINES_SETTING_KEY, _handle_excluded_disciplines_setting)
register_setting_hook(IDP_EXCLUDED_UNITS_SETTING_KEY, _handle_excluded_units_setting)

register_module(
    "idp",
    ModuleDefinition(
        to_incremental_records=to_incremental_records,
        delegate_factory=IdpDelegate,
        recalc_indicators=recalc_idp_indicators,
    ),
)
