"""Rotas do módulo RNC — `/rnc`, `/rnc/registros`, `/publicacoes/rnc`.

Porte de `src/app/api/rnc/route.ts`, `src/app/api/rnc/registros/route.ts` e
`src/app/api/publicacoes/rnc/route.ts`. Registra o módulo no motor de
importação genérico (`app/modules/imports/registry.py`) na importação deste
arquivo — ver `register_module` ao final.
"""

from __future__ import annotations

import math
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.errors import DomainError, NotFoundError
from app.core.permissions import Permission
from app.models.common import utcnow
from app.models.indicators import IndicatorPublication, IndicatorResult
from app.models.records import RncRecord
from app.modules.imports.registry import ModuleDefinition, register_module
from app.modules.rnc.calculations import compute_rnc_result
from app.modules.rnc.publications import to_rnc_published_payload
from app.modules.rnc.repository import (
    RncDelegate,
    count_records,
    load_all_records,
    load_last_import,
    load_rnc_configuration,
    save_rnc_configuration,
)
from app.modules.rnc.schemas import (
    PeriodRangeOut,
    PublishedByOut,
    RncDeleteIn,
    RncDeleteOut,
    RncEditIn,
    RncEditOut,
    RncEditUpdatedOut,
    RncGetOut,
    RncLastImportOut,
    RncMonthAggregateOut,
    RncOfensorAggregateOut,
    RncPatchSettingsIn,
    RncPatchSettingsOut,
    RncPublicationDetailOut,
    RncPublicationOut,
    RncPublicationsGetOut,
    RncPublishIn,
    RncRecordsCountOut,
    RncResultOut,
    RncUnitAggregateOut,
)
from app.modules.rnc.service import normalize_excluded_units, recalc_rnc_indicators, to_incremental_records
from app.modules.rnc.types import (
    RNC_DEFAULT_MAX_DIAS,
    RNC_INDICATOR,
    RNC_MODULE,
    RncNormalizedRecord,
    RncResult,
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


def _record_to_normalized(r: RncRecord) -> RncNormalizedRecord:
    return RncNormalizedRecord(
        status_rnc=r.statusRnc,
        unidade=r.unidade,
        data_criacao=r.dataCriacao,
        data_solucao=r.dataSolucao,
        tempo_tratativa=r.tempoTratativa,
        ofensor=r.ofensor,
        year=r.year,
        month=r.month,
        raw=r.raw,
    )


def _parse_meta(value: str | None) -> float:
    """`parseMeta`: `Number(value)`; usa o valor se finito e `>= 0`, senão
    cai para `RNC_DEFAULT_MAX_DIAS` (15)."""
    if value is None:
        return RNC_DEFAULT_MAX_DIAS
    try:
        num = float(value)
    except ValueError:
        return RNC_DEFAULT_MAX_DIAS
    if math.isfinite(num) and num >= 0:
        return num
    return RNC_DEFAULT_MAX_DIAS


def _result_out(result: RncResult) -> RncResultOut:
    return RncResultOut(
        meta_dias=result.meta_dias,
        excluded_units=result.excluded_units,
        period=PeriodRangeOut(
            start_year=result.period.start_year,
            start_month=result.period.start_month,
            end_year=result.period.end_year,
            end_month=result.period.end_month,
        )
        if result.period
        else None,
        total_criadas=result.total_criadas,
        total_tratadas=result.total_tratadas,
        aderencia_total=result.aderencia_total,
        resultado_dias=result.resultado_dias,
        months=[
            RncMonthAggregateOut(
                year=m.year, month=m.month, label=m.label, chamados=m.chamados,
                solucionados=m.solucionados, dias_medios=m.dias_medios, dentro_meta=m.dentro_meta,
            )
            for m in result.months
        ],
        units=[
            RncUnitAggregateOut(
                name=u.name, criadas=u.criadas, tratadas=u.tratadas, aderencia=u.aderencia,
                tempos_tratativa=u.tempos_tratativa, dias_medios=u.dias_medios,
                dias_medianos=u.dias_medianos, tratativas_com_tempo=u.tratativas_com_tempo,
                maior_tempo_tratativa=u.maior_tempo_tratativa, principal_ofensor=u.principal_ofensor,
                principal_ofensor_count=u.principal_ofensor_count, excluded=u.excluded,
            )
            for u in result.units
        ],
        ofensores=[
            RncOfensorAggregateOut(name=o.name, count=o.count, pct=o.pct) for o in result.ofensores
        ],
    )


@router.get("/rnc", response_model=RncGetOut)
async def get_rnc(
    meta: str | None = Query(default=None),
    period: Annotated[PeriodRange | None, Depends(period_range_query)] = None,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_READ)),
) -> RncGetOut:
    meta_dias = _parse_meta(meta)

    rows = await load_all_records(session)
    total = len(rows)
    last_import = await load_last_import(session)
    configuration = await load_rnc_configuration(session)

    records = [_record_to_normalized(r) for r in rows]
    result = compute_rnc_result(records, meta_dias, configuration.excluded_units, period)

    return RncGetOut(
        total=total,
        meta_dias=meta_dias,
        result=_result_out(result),
        last_import=RncLastImportOut(
            id=last_import.id, file_name=last_import.fileName, completed_at=last_import.completedAt,
            total_found=last_import.totalFound, total_inserted=last_import.totalInserted,
            total_updated=last_import.totalUpdated, total_ignored=last_import.totalIgnored,
            total_rejected=last_import.totalRejected,
        )
        if last_import
        else None,
    )


@router.patch("/rnc", response_model=RncPatchSettingsOut)
async def patch_rnc_settings(
    body: RncPatchSettingsIn,
    session: AsyncSession = Depends(get_session),
    # Divergência #1 do inventário: esta rota usa `import:run` (ANALYST ou
    # ADMIN), NÃO `indicators:edit` — preservado por paridade.
    current_user: CurrentUser = Depends(require_permission(Permission.IMPORT_RUN)),
) -> RncPatchSettingsOut:
    excluded_units = normalize_excluded_units(list(body.excluded_units))
    await save_rnc_configuration(session, excluded_units)
    await recalc_rnc_indicators(session)
    await record_audit(
        session,
        user_id=current_user.id,
        action="INDICATOR_SETTINGS_UPDATED",
        entity="AppSetting",
        entity_id="rnc",
        new_data={"excludedUnits": excluded_units},
        metadata={"module": "rnc"},
    )
    await session.commit()
    return RncPatchSettingsOut(ok=True, excluded_units=excluded_units)


@router.get("/rnc/registros", response_model=RncRecordsCountOut)
async def get_rnc_registros_count(
    period: Annotated[PeriodRange | None, Depends(period_range_query)] = None,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_EDIT)),
) -> RncRecordsCountOut:
    filters = [period_range_predicate(period, RncRecord.year, RncRecord.month)] if period else []
    count = await count_records(session, filters)
    return RncRecordsCountOut(count=count)


@router.patch("/rnc/registros", response_model=RncEditOut)
async def patch_rnc_registro(
    body: RncEditIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_EDIT)),
) -> RncEditOut:
    """Só `statusRnc`/`tempoTratativa` são editáveis — `unidade`, datas e
    `ofensor` compõem a identidade/origem e não são expostos aqui. Um campo
    ausente do JSON não é tocado; presente (mesmo `tempoTratativa: null`)
    substitui o valor atual. **Não** chama `recalc_rnc_indicators`
    (Divergência #2 do inventário: `IndicatorResult` fica desatualizado até
    o próximo gatilho de recálculo)."""
    existing = await session.get(RncRecord, body.id)
    if existing is None:
        raise NotFoundError("Registro não encontrado.")

    provided = body.model_fields_set
    status_provided = "status" in provided
    tempo_provided = "tempo_tratativa" in provided

    no_change = (not status_provided or body.status == existing.statusRnc) and (
        not tempo_provided or body.tempo_tratativa == existing.tempoTratativa
    )
    if no_change:
        return RncEditOut(ok=True, unchanged=True)

    previous = {"statusRnc": existing.statusRnc, "tempoTratativa": existing.tempoTratativa}

    if status_provided and body.status is not None:
        existing.statusRnc = body.status
    if tempo_provided:
        existing.tempoTratativa = body.tempo_tratativa
    existing.editedManually = True
    existing.editedBy = current_user.id
    existing.editedAt = utcnow()
    await session.flush()

    await record_audit(
        session,
        user_id=current_user.id,
        action="RECORD_EDITED",
        entity="RncRecord",
        entity_id=body.id,
        previous_data=previous,
        new_data={"statusRnc": existing.statusRnc, "tempoTratativa": existing.tempoTratativa},
        metadata={"module": "rnc", "unidade": existing.unidade},
    )
    await session.commit()

    updated = RncEditUpdatedOut(
        id=existing.id, status_rnc=existing.statusRnc, tempo_tratativa=existing.tempoTratativa
    )
    return RncEditOut(ok=True, updated=updated)


@router.delete("/rnc/registros", response_model=RncDeleteOut)
async def delete_rnc_registros(
    body: RncDeleteIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_EDIT)),
) -> RncDeleteOut:
    """A publicação vigente não é apagada: é um snapshot histórico imutável.
    Três comportamentos DIFERENTES de recálculo, preservados por paridade
    (Divergência #3 do inventário): `all` apaga também `IndicatorResult` sem
    recalcular; `period` apaga e recalcula; `ids` apaga e NÃO recalcula."""
    if body.mode == "all":
        count = await count_records(session, [])
        if count == 0:
            return RncDeleteOut(ok=True, deleted=0)

        await session.execute(delete(RncRecord))
        await session.execute(delete(IndicatorResult).where(IndicatorResult.module == RNC_MODULE))
        await record_audit(
            session,
            user_id=current_user.id,
            action="RECORDS_CLEARED",
            entity="RncRecord",
            previous_data={"quantidade": count},
            metadata={"module": "rnc", "escopo": "todos"},
        )
        await session.commit()
        return RncDeleteOut(ok=True, deleted=count)

    if body.mode == "period":
        range_ = _period_from_fields(
            body.period_start_year, body.period_start_month, body.period_end_year, body.period_end_month
        )
        if range_ is None:
            raise DomainError("Período incompleto.")
        filters = [period_range_predicate(range_, RncRecord.year, RncRecord.month)]
        count = await count_records(session, filters)
        if count == 0:
            return RncDeleteOut(ok=True, deleted=0)

        await session.execute(delete(RncRecord).where(*filters))
        await recalc_rnc_indicators(session)
        await record_audit(
            session,
            user_id=current_user.id,
            action="RECORDS_CLEARED",
            entity="RncRecord",
            previous_data={"quantidade": count},
            metadata={"module": "rnc", "escopo": "periodo", "periodo": format_period_range_label(range_)},
        )
        await session.commit()
        return RncDeleteOut(ok=True, deleted=count)

    # mode == "ids" — não recalcula IndicatorResult (paridade com o TS original).
    ids = body.ids or []
    to_delete_result = await session.execute(select(RncRecord).where(RncRecord.id.in_(ids)))
    to_delete = list(to_delete_result.scalars().all())

    result = cast(CursorResult, await session.execute(delete(RncRecord).where(RncRecord.id.in_(ids))))

    await record_audit(
        session,
        user_id=current_user.id,
        action="RECORD_DELETED",
        entity="RncRecord",
        entity_id=",".join(ids),
        previous_data={
            "registros": [
                {
                    "id": r.id,
                    "unidade": r.unidade,
                    "status": r.statusRnc,
                    "ofensor": r.ofensor,
                    "dataCriacao": r.dataCriacao.isoformat(),
                }
                for r in to_delete
            ]
        },
        metadata={"module": "rnc", "quantidade": result.rowcount},
    )
    await session.commit()
    return RncDeleteOut(ok=True, deleted=result.rowcount or 0)


def _publication_out(pub: IndicatorPublication) -> RncPublicationDetailOut:
    return RncPublicationDetailOut(
        id=pub.id, version=pub.version, target=pub.target, result=pub.result, status=pub.status,
        payload=pub.payload, published_at=pub.publishedAt,
        published_by=PublishedByOut(
            id=pub.publishedBy.id, name=pub.publishedBy.name, email=pub.publishedBy.email
        ),
    )


@router.get("/publicacoes/rnc", response_model=RncPublicationsGetOut)
async def get_publicacoes_rnc(
    period: Annotated[PeriodRange | None, Depends(period_range_query)] = None,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_READ)),
) -> RncPublicationsGetOut:
    result = await session.execute(
        select(IndicatorPublication)
        .where(IndicatorPublication.module == RNC_MODULE, IndicatorPublication.indicator == RNC_INDICATOR)
        .order_by(IndicatorPublication.publishedAt.desc(), IndicatorPublication.version.desc())
        .options(selectinload(IndicatorPublication.publishedBy))
    )
    all_versions = list(result.scalars().all())
    publication, history_count = select_publication_for_period(all_versions, period)  # type: ignore[type-var]

    return RncPublicationsGetOut(
        publication=_publication_out(publication) if publication else None,
        history_count=history_count,
    )


@router.post("/publicacoes/rnc", response_model=RncPublicationOut)
async def post_publicacoes_rnc(
    body: RncPublishIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_PUBLISH)),
) -> RncPublicationOut:
    rows = await load_all_records(session)
    if not rows:
        raise DomainError("Não há registros de RNC para publicar.")

    configuration = await load_rnc_configuration(session)

    period = _period_from_fields(
        body.period_start_year, body.period_start_month, body.period_end_year, body.period_end_month
    )
    cycle = resolve_publication_cycle(period)

    records = [_record_to_normalized(r) for r in rows]
    result = compute_rnc_result(records, body.meta_dias, configuration.excluded_units, period)
    if result.resultado_dias is None:
        raise DomainError("Não há RNC solucionada com Tempo de Tratativa numérico para publicar.")

    payload = to_rnc_published_payload(result)
    status = "OK" if payload["resultado"] <= payload["meta"] else "FORA"

    latest_result = await session.execute(
        select(IndicatorPublication.version)
        .where(IndicatorPublication.module == RNC_MODULE, IndicatorPublication.indicator == RNC_INDICATOR)
        .order_by(IndicatorPublication.version.desc())
        .limit(1)
    )
    latest_version = latest_result.scalar_one_or_none()
    version = (latest_version or 0) + 1

    deactivate_filters = [
        IndicatorPublication.module == RNC_MODULE,
        IndicatorPublication.indicator == RNC_INDICATOR,
        IndicatorPublication.active == True,  # noqa: E712
    ]
    if cycle:
        deactivate_filters.append(IndicatorPublication.cycleYear == cycle.year)
        deactivate_filters.append(IndicatorPublication.cycleSemester == cycle.semester.value)
    await session.execute(update(IndicatorPublication).where(*deactivate_filters).values(active=False))

    publication = IndicatorPublication(
        module=RNC_MODULE,
        indicator=RNC_INDICATOR,
        version=version,
        target=body.meta_dias,
        result=payload["resultado"],
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
            "module": RNC_MODULE, "indicator": RNC_INDICATOR, "version": version,
            "target": payload["meta"], "result": payload["resultado"], "status": status,
        },
        metadata={
            "totalCriadas": payload["semestreTotal"], "totalTratadas": payload["semestreResolvidas"],
            "unidades": len(payload["unidades"]), "meses": len(payload["mensal"]),
        },
    )
    await session.commit()

    return RncPublicationOut(publication=_publication_out(publication))


register_module(
    "rnc",
    ModuleDefinition(
        to_incremental_records=to_incremental_records,
        delegate_factory=RncDelegate,
        recalc_indicators=recalc_rnc_indicators,
    ),
)
