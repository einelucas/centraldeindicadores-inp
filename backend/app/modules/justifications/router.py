"""Rotas de justificativas — `/justificativas`, `/justificativas/sugestao`.

Porte de `src/app/api/justificativas/**`. Todas as rotas exigem
`import:run` (não uma permissão dedicada) — mesma matriz do TS original
(ver inventário, seção "Rotas de justificativas": ANALYST e ADMIN acessam,
VIEWER recebe 403 mesmo para leitura).

`GET /justificativas/sugestao` recalcula o indicador do zero a partir das
tabelas de registros brutos por módulo (RDO/IDP/RNC/5S) ou dos lançamentos
manuais (Taxa de Acidentes), com os mesmos 5 geradores de evidência/texto do
TS original (`app/modules/justifications/generators/*.py`) — não é mais uma
versão simplificada que recebia `result`/`evidence` já computados pelo
chamador (essa era uma decisão de escopo tomada antes de RDO/IDP/RNC
existirem em Python; agora que os 5 módulos existem, a rota foi reescrita
para paridade real com `src/app/api/justificativas/sugestao/route.ts`,
inclusive o método HTTP — GET com query string, não POST com corpo)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission
from app.models.imports import ImportJob, ImportStatus
from app.models.indicators import IndicatorJustification
from app.models.records import FiveSRecord, IdpRsoRecord, RdoRecord, RncRecord
from app.models.user import User
from app.modules.cinco_s.calculations import compute_five_s_result
from app.modules.cinco_s.repository import load_five_s_configuration, record_from_row
from app.modules.idp.calculations import compute_idp_result
from app.modules.idp.repository import load_idp_configuration, reconstruct_records
from app.modules.justifications import service
from app.modules.justifications.generators.cinco_s import generate_five_s_justification
from app.modules.justifications.generators.idp import generate_idp_justification
from app.modules.justifications.generators.rdo import generate_rdo_justification
from app.modules.justifications.generators.rnc import generate_rnc_justification
from app.modules.justifications.generators.taxa_acidentes import generate_accident_rate_justification
from app.modules.justifications.schemas import (
    DeleteJustificationOut,
    EvidenceItem,
    JustificationListOut,
    JustificationModule,
    JustificationOut,
    NameOut,
    SaveJustificationIn,
    SaveJustificationOut,
    SourceImportIn,
    SuggestionOut,
    SuggestionResponseOut,
)
from app.modules.justifications.types import Suggestion
from app.modules.rdo.repository import load_rdo_configuration
from app.modules.rdo.types import RdoNormalizedRecord
from app.modules.rnc.calculations import compute_rnc_result
from app.modules.rnc.repository import load_rnc_configuration
from app.modules.rnc.types import RncNormalizedRecord
from app.modules.taxa_acidentes.calculations import compute_accident_rate_result
from app.modules.taxa_acidentes.service import load_accident_rate_data
from app.shared.period import PeriodRange

router = APIRouter()


def _build_out(
    record: IndicatorJustification, creator: User | None, updater: User | None
) -> JustificationOut:
    return JustificationOut(
        id=record.id,
        module=record.module,
        year=record.year,
        month=record.month,
        result=record.result,
        target=record.target,
        status=record.status,
        evidence=[EvidenceItem(**item) for item in (record.evidence or [])],
        suggested_text=record.suggestedText,
        text=record.text,
        source_import_id=record.sourceImportId,
        source_imported_at=record.sourceImportedAt,
        created_at=record.createdAt,
        updated_at=record.updatedAt,
        created_by=NameOut(name=creator.name) if creator is not None else None,
        updated_by=NameOut(name=updater.name) if updater is not None else None,
    )


@router.get("/justificativas", response_model=JustificationListOut)
async def list_justificativas(
    module: JustificationModule = Query(...),
    year: int = Query(..., ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.IMPORT_RUN)),
) -> JustificationListOut:
    rows = await service.list_justifications(session, module=module, year=year, month=month)
    return JustificationListOut(records=[_build_out(r, creator, updater) for r, creator, updater in rows])


@router.put("/justificativas", response_model=SaveJustificationOut)
async def put_justificativas(
    body: SaveJustificationIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.IMPORT_RUN)),
) -> SaveJustificationOut:
    record = await service.save_justification(
        session,
        module=body.module,
        year=body.year,
        month=body.month,
        text=body.text,
        suggested_text=body.suggested_text,
        result=body.result,
        target=body.target,
        status=body.status,
        evidence=body.evidence,
        source_import=body.source_import,
        user=current_user,
    )
    creator = await session.get(User, record.createdById)
    updater = await session.get(User, record.updatedById)
    return SaveJustificationOut(record=_build_out(record, creator, updater))


@router.delete("/justificativas", response_model=DeleteJustificationOut)
async def delete_justificativas(
    module: JustificationModule = Query(...),
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.IMPORT_RUN)),
) -> DeleteJustificationOut:
    await service.delete_justification(session, module=module, year=year, month=month, user=current_user)
    return DeleteJustificationOut()


# --- GET /justificativas/sugestao ---------------------------------------------------


def _previous_month_year(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


async def _source_import(
    session: AsyncSession, module: str, year: int, month: int, *, allow_null_reference: bool
) -> SourceImportIn | None:
    filters = [
        ImportJob.module == module,
        ImportJob.status.in_([ImportStatus.COMPLETED, ImportStatus.COMPLETED_WITH_ERRORS]),
    ]
    if allow_null_reference:
        filters.append(
            or_(
                and_(ImportJob.referenceYear == year, ImportJob.referenceMonth == month),
                ImportJob.referenceYear.is_(None),
            )
        )
    else:
        filters.extend([ImportJob.referenceYear == year, ImportJob.referenceMonth == month])

    result = await session.execute(
        select(ImportJob).where(*filters).order_by(ImportJob.completedAt.desc()).limit(1)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return None
    return SourceImportIn(id=job.id, imported_at=job.completedAt)


def _rdo_normalized(row: RdoRecord) -> RdoNormalizedRecord:
    return RdoNormalizedRecord(
        data_referencia=row.dataReferencia, empresa_nome=row.empresaNome,
        status_descricao=row.statusDescricao, relatorio_id=row.relatorioId, grupo=row.grupo,
        disciplina=row.disciplina, year=row.year, month=row.month, raw=row.raw,
    )


def _rnc_normalized(row: RncRecord) -> RncNormalizedRecord:
    return RncNormalizedRecord(
        status_rnc=row.statusRnc, unidade=row.unidade, data_criacao=row.dataCriacao,
        data_solucao=row.dataSolucao, tempo_tratativa=row.tempoTratativa, ofensor=row.ofensor,
        year=row.year, month=row.month, raw=row.raw,
    )


async def _generate_rdo(session: AsyncSession, year: int, month: int, target: float) -> Suggestion:
    prev_year, prev_month = _previous_month_year(year, month)
    rows_result = await session.execute(
        select(RdoRecord).where(RdoRecord.year == year, RdoRecord.month == month)
    )
    prev_rows_result = await session.execute(
        select(RdoRecord).where(RdoRecord.year == prev_year, RdoRecord.month == prev_month)
    )
    configuration = await load_rdo_configuration(session)
    source_import = await _source_import(session, "rdo", year, month, allow_null_reference=True)

    return generate_rdo_justification(
        records=[_rdo_normalized(r) for r in rows_result.scalars().all()],
        previous_records=[_rdo_normalized(r) for r in prev_rows_result.scalars().all()],
        year=year, month=month, threshold=target / 100,
        excluded_units=configuration.excluded_units, source_import=source_import,
    )


async def _generate_rnc(session: AsyncSession, year: int, month: int, target: float) -> Suggestion:
    prev_year, prev_month = _previous_month_year(year, month)
    rows_result = await session.execute(
        select(RncRecord).where(
            or_(
                and_(RncRecord.year == year, RncRecord.month == month),
                and_(RncRecord.year == prev_year, RncRecord.month == prev_month),
            )
        )
    )
    records = [_rnc_normalized(r) for r in rows_result.scalars().all()]
    configuration = await load_rnc_configuration(session)
    source_import = await _source_import(session, "rnc", year, month, allow_null_reference=True)

    result = compute_rnc_result(
        records, target, configuration.excluded_units, PeriodRange(year, month, year, month)
    )
    previous_result = compute_rnc_result(
        records, target, configuration.excluded_units,
        PeriodRange(prev_year, prev_month, prev_year, prev_month),
    )
    return generate_rnc_justification(
        result=result, previous_result=previous_result, year=year, month=month,
        source_import=source_import,
    )


async def _generate_five_s(session: AsyncSession, year: int, month: int, target: float) -> Suggestion:
    prev_year, prev_month = _previous_month_year(year, month)
    rows_result = await session.execute(
        select(FiveSRecord).where(
            or_(
                and_(FiveSRecord.year == year, FiveSRecord.month == month),
                and_(FiveSRecord.year == prev_year, FiveSRecord.month == prev_month),
            )
        )
    )
    records = [record_from_row(r) for r in rows_result.scalars().all()]
    _threshold_setting, excluded_units = await load_five_s_configuration(session)
    source_import = await _source_import(session, "cinco-s", year, month, allow_null_reference=True)

    threshold = target / 100
    result = compute_five_s_result(records, excluded_units, threshold, PeriodRange(year, month, year, month))
    previous_result = compute_five_s_result(
        records, excluded_units, threshold,
        PeriodRange(prev_year, prev_month, prev_year, prev_month),
    )
    return generate_five_s_justification(
        result=result, previous_result=previous_result, year=year, month=month,
        source_import=source_import,
    )


async def _generate_idp(session: AsyncSession, year: int, month: int, target: float) -> Suggestion:
    prev_year, prev_month = _previous_month_year(year, month)
    rows_result = await session.execute(
        select(IdpRsoRecord).where(
            or_(
                and_(IdpRsoRecord.referenceYear == year, IdpRsoRecord.referenceMonth == month),
                and_(IdpRsoRecord.referenceYear == prev_year, IdpRsoRecord.referenceMonth == prev_month),
            )
        )
    )
    pairs, _invalid = reconstruct_records(list(rows_result.scalars().all()))
    records = [record for _row, record in pairs]
    configuration = await load_idp_configuration(session)
    source_import = await _source_import(session, "idp", year, month, allow_null_reference=False)

    threshold = target / 100
    result = compute_idp_result(
        records, threshold, configuration.excluded_disciplines, configuration.excluded_units,
        PeriodRange(year, month, year, month),
    )
    previous_result = compute_idp_result(
        records, threshold, configuration.excluded_disciplines, configuration.excluded_units,
        PeriodRange(prev_year, prev_month, prev_year, prev_month),
    )
    return generate_idp_justification(
        result=result, previous_result=previous_result, source_import=source_import
    )


async def _generate_accident_rate(
    session: AsyncSession, year: int, month: int, target: float
) -> Suggestion:
    prev_year, prev_month = _previous_month_year(year, month)
    data = await load_accident_rate_data(session)

    result = compute_accident_rate_result(
        data.monthly, data.units, target, data.excluded_units, PeriodRange(year, month, year, month)
    )
    previous_result = compute_accident_rate_result(
        data.monthly, data.units, target, data.excluded_units,
        PeriodRange(prev_year, prev_month, prev_year, prev_month),
    )
    return generate_accident_rate_justification(
        result=result, previous_result=previous_result, year=year, month=month, source_import=None
    )


@router.get("/justificativas/sugestao", response_model=SuggestionResponseOut)
async def sugestao_justificativa(
    module: JustificationModule = Query(...),
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    target: float = Query(default=80.0, ge=0, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.IMPORT_RUN)),
) -> SuggestionResponseOut:
    if module == "idp":
        suggestion = await _generate_idp(session, year, month, target)
    elif module == "rnc":
        suggestion = await _generate_rnc(session, year, month, target)
    elif module == "cinco-s":
        suggestion = await _generate_five_s(session, year, month, target)
    elif module == "taxa-acidentes":
        suggestion = await _generate_accident_rate(session, year, month, target)
    else:
        suggestion = await _generate_rdo(session, year, month, target)

    return SuggestionResponseOut(
        suggestion=SuggestionOut(
            module=suggestion.module, year=suggestion.year, month=suggestion.month,
            result=suggestion.result, target=suggestion.target, status=suggestion.status,
            evidence=suggestion.evidence, suggested_text=suggestion.suggested_text,
            source_import=suggestion.source_import,
        )
    )
