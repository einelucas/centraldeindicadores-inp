"""Rotas genéricas de importação incremental — `/api/v1/importacoes/...`.

Porte de `src/app/api/importacoes/**`. Roteia por `module` através do
registro em `app/modules/imports/registry.py`, populado pelos módulos
rdo/idp/rnc/cinco_s no import de seus respectivos `router.py`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.config import get_settings
from app.core.database import get_session
from app.core.errors import DomainError, NotFoundError
from app.core.permissions import Permission
from app.models.imports import ImportBatch, ImportJob
from app.models.imports import ImportError as ImportErrorRow
from app.modules.imports import service
from app.modules.imports.registry import get_module_definition
from app.modules.imports.schemas import (
    BatchErrorOut,
    BatchIn,
    BatchOut,
    FinalizeOut,
    FinalizeTotalsOut,
    ImportBatchOut,
    ImportErrorOut,
    ImportErrorsOut,
    ImportJobOut,
    StartImportIn,
    StartImportOut,
)

router = APIRouter(prefix="/importacoes", tags=["importacoes"])


@router.post("/iniciar", response_model=StartImportOut)
async def iniciar(
    body: StartImportIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.IMPORT_RUN)),
) -> StartImportOut:
    if get_module_definition(body.module) is None:
        raise DomainError(f"Módulo '{body.module}' não está ativo para importação.")

    job = await service.start_import_job(
        session,
        module=body.module,
        file_name=body.file_name,
        reference_year=body.reference_year,
        reference_month=body.reference_month,
        total_found=body.total_found,
        user_id=current_user.id,
    )
    return StartImportOut(import_job_id=job.id, status=job.status.value)


@router.post("/{job_id}/lotes", response_model=BatchOut)
async def lotes(
    job_id: str,
    body: BatchIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.IMPORT_RUN)),
) -> BatchOut:
    job = await session.get(ImportJob, job_id)
    if job is None:
        raise NotFoundError("Job de importação não encontrado.")

    definition = get_module_definition(job.module)
    if definition is None:
        raise HTTPException(status_code=501, detail=f"Módulo '{job.module}' não implementado.")

    settings = get_settings()
    if len(body.records) > settings.max_import_records_per_batch:
        raise DomainError("Lote excede o limite de registros.")

    records, schema_rejected = definition.to_incremental_records(body.records)

    outcome, already_processed = await service.process_batch(
        session,
        import_job_id=job_id,
        batch_number=body.batch_number,
        records=records,
        delegate_factory=definition.delegate_factory,
    )

    return BatchOut(
        inserted=outcome.inserted,
        ignored=outcome.ignored,
        updated=outcome.updated,
        rejected=outcome.rejected + (0 if already_processed else schema_rejected),
        errors=[BatchErrorOut(business_key=e.business_key, message=e.message) for e in outcome.errors],
        already_processed=already_processed,
    )


@router.post("/{job_id}/finalizar", response_model=FinalizeOut)
async def finalizar(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.IMPORT_RUN)),
) -> FinalizeOut:
    job_before = await session.get(ImportJob, job_id)
    if job_before is None:
        raise NotFoundError("Job de importação não encontrado.")

    definition = get_module_definition(job_before.module)
    recalc = definition.recalc_indicators if definition is not None else None

    job = await service.finalize_import_job(
        session, import_job_id=job_id, user_id=current_user.id, recalc_indicators=recalc
    )
    return FinalizeOut(
        status=job.status.value,
        totals=FinalizeTotalsOut(
            found=job.totalFound,
            inserted=job.totalInserted,
            ignored=job.totalIgnored,
            updated=job.totalUpdated,
            rejected=job.totalRejected,
        ),
    )


@router.get("/{job_id}", response_model=ImportJobOut)
async def get_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.IMPORT_READ)),
) -> ImportJobOut:
    job = await session.get(ImportJob, job_id)
    if job is None:
        raise NotFoundError("Job de importação não encontrado.")

    batches_result = await session.execute(
        select(ImportBatch).where(ImportBatch.importJobId == job_id).order_by(ImportBatch.batchNumber)
    )
    batches = batches_result.scalars().all()

    return ImportJobOut(
        id=job.id,
        module=job.module,
        file_name=job.fileName,
        reference_year=job.referenceYear,
        reference_month=job.referenceMonth,
        status=job.status.value,
        total_found=job.totalFound,
        total_inserted=job.totalInserted,
        total_ignored=job.totalIgnored,
        total_updated=job.totalUpdated,
        total_rejected=job.totalRejected,
        started_at=job.startedAt,
        completed_at=job.completedAt,
        user_id=job.userId,
        batches=[
            ImportBatchOut(
                id=b.id,
                batch_number=b.batchNumber,
                total_received=b.totalReceived,
                total_inserted=b.totalInserted,
                total_ignored=b.totalIgnored,
                total_updated=b.totalUpdated,
                total_rejected=b.totalRejected,
                processed_at=b.processedAt,
            )
            for b in batches
        ],
    )


@router.get("/{job_id}/erros", response_model=ImportErrorsOut)
async def get_erros(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.IMPORT_READ)),
) -> ImportErrorsOut:
    result = await session.execute(
        select(ImportErrorRow)
        .where(ImportErrorRow.importJobId == job_id)
        .order_by(ImportErrorRow.createdAt)
        .limit(500)
    )
    items = result.scalars().all()
    return ImportErrorsOut(
        items=[
            ImportErrorOut(
                id=e.id,
                batch_number=e.batchNumber,
                row_number=e.rowNumber,
                field=e.field,
                message=e.message,
                raw_data=e.rawData,
                created_at=e.createdAt,
            )
            for e in items
        ]
    )


@router.get("", response_model=list[ImportJobOut])
async def list_jobs(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.IMPORT_READ)),
) -> list[ImportJobOut]:
    result = await session.execute(select(ImportJob).order_by(ImportJob.startedAt.desc()))
    jobs = result.scalars().all()
    return [
        ImportJobOut(
            id=j.id,
            module=j.module,
            file_name=j.fileName,
            reference_year=j.referenceYear,
            reference_month=j.referenceMonth,
            status=j.status.value,
            total_found=j.totalFound,
            total_inserted=j.totalInserted,
            total_ignored=j.totalIgnored,
            total_updated=j.totalUpdated,
            total_rejected=j.totalRejected,
            started_at=j.startedAt,
            completed_at=j.completedAt,
            user_id=j.userId,
            batches=[],
        )
        for j in jobs
    ]
