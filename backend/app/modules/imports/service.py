"""Serviço de importação genérico. Porte de `src/server/services/import-service.ts`.

Orquestra ImportJob -> ImportBatch (idempotente) -> finalização. Cada
sub-lote de até 50 registros roda em sua própria transação curta — evita
manter uma transação remota gigante (mesmo motivo do original: bancos
gerenciados podem expirar transações longas). Reenvio do mesmo
`(importJobId, batchNumber)` é seguro: o índice único faz a segunda tentativa
"perder a corrida" sob concorrência, e nesse caso devolvemos o resultado já
persistido em vez de propagar o erro.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.imports import ImportBatch, ImportJob, ImportStatus
from app.models.imports import ImportError as ImportErrorRow
from app.modules.imports.registry import DelegateFactory
from app.shared.audit import record_audit
from app.shared.incremental_upsert import IncrementalRecord, UpsertOutcome, process_incremental_batch

SERVER_TRANSACTION_CHUNK_SIZE = 50


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def start_import_job(
    session: AsyncSession,
    *,
    module: str,
    file_name: str,
    reference_year: int | None,
    reference_month: int | None,
    total_found: int,
    user_id: str,
) -> ImportJob:
    job = ImportJob(
        module=module,
        fileName=file_name[:300],
        referenceYear=reference_year,
        referenceMonth=reference_month,
        totalFound=total_found,
        status=ImportStatus.PROCESSING,
        userId=user_id,
    )
    session.add(job)
    await session.flush()
    await record_audit(
        session,
        user_id=user_id,
        action="IMPORT_STARTED",
        entity="ImportJob",
        entity_id=job.id,
        metadata={"module": module, "fileName": job.fileName},
    )
    await session.commit()
    await session.refresh(job)
    return job


async def _load_batch(session: AsyncSession, import_job_id: str, batch_number: int) -> ImportBatch | None:
    result = await session.execute(
        select(ImportBatch).where(
            ImportBatch.importJobId == import_job_id, ImportBatch.batchNumber == batch_number
        )
    )
    return result.scalar_one_or_none()


def _outcome_from_batch(batch: ImportBatch) -> UpsertOutcome:
    return UpsertOutcome(
        inserted=batch.totalInserted,
        ignored=batch.totalIgnored,
        updated=batch.totalUpdated,
        rejected=batch.totalRejected,
    )


async def process_batch(
    session: AsyncSession,
    *,
    import_job_id: str,
    batch_number: int,
    records: list[IncrementalRecord],
    delegate_factory: DelegateFactory,
) -> tuple[UpsertOutcome, bool]:
    """Retorna (outcome, already_processed)."""
    existing_batch = await _load_batch(session, import_job_id, batch_number)
    if existing_batch is not None:
        return _outcome_from_batch(existing_batch), True

    outcome = UpsertOutcome()
    for offset in range(0, len(records), SERVER_TRANSACTION_CHUNK_SIZE):
        sub_chunk = records[offset : offset + SERVER_TRANSACTION_CHUNK_SIZE]
        delegate = delegate_factory(session)
        partial = await process_incremental_batch(sub_chunk, delegate, import_job_id)
        outcome.inserted += partial.inserted
        outcome.ignored += partial.ignored
        outcome.updated += partial.updated
        outcome.rejected += partial.rejected
        outcome.errors.extend(partial.errors)
        await session.commit()

    try:
        session.add(
            ImportBatch(
                importJobId=import_job_id,
                batchNumber=batch_number,
                totalReceived=len(records),
                totalInserted=outcome.inserted,
                totalIgnored=outcome.ignored,
                totalUpdated=outcome.updated,
                totalRejected=outcome.rejected,
            )
        )
        for error in outcome.errors:
            session.add(
                ImportErrorRow(
                    importJobId=import_job_id,
                    batchNumber=batch_number,
                    field="businessKey",
                    message=error.message,
                    rawData={"businessKey": error.business_key},
                )
            )

        job = await session.get(ImportJob, import_job_id)
        if job is None:
            raise NotFoundError("Job de importação não encontrado.")
        job.totalInserted += outcome.inserted
        job.totalIgnored += outcome.ignored
        job.totalUpdated += outcome.updated
        job.totalRejected += outcome.rejected
        await session.commit()
    except IntegrityError:
        await session.rollback()
        completed_batch = await _load_batch(session, import_job_id, batch_number)
        if completed_batch is not None:
            return _outcome_from_batch(completed_batch), True
        raise

    return outcome, False


async def finalize_import_job(
    session: AsyncSession,
    *,
    import_job_id: str,
    user_id: str,
    recalc_indicators: Callable[[AsyncSession], Awaitable[None]] | None = None,
) -> ImportJob:
    job = await session.get(ImportJob, import_job_id)
    if job is None:
        raise NotFoundError("Job de importação não encontrado.")

    if recalc_indicators is not None:
        await recalc_indicators(session)

    job.status = ImportStatus.COMPLETED_WITH_ERRORS if job.totalRejected > 0 else ImportStatus.COMPLETED
    job.completedAt = _utcnow()
    await session.flush()

    await record_audit(
        session,
        user_id=user_id,
        action="IMPORT_COMPLETED",
        entity="ImportJob",
        entity_id=import_job_id,
        metadata={
            "status": job.status.value,
            "inserted": job.totalInserted,
            "updated": job.totalUpdated,
            "ignored": job.totalIgnored,
            "rejected": job.totalRejected,
        },
    )
    await session.commit()
    await session.refresh(job)
    return job


async def fail_import_job(session: AsyncSession, import_job_id: str, message: str) -> None:
    job = await session.get(ImportJob, import_job_id)
    if job is None:
        return
    job.status = ImportStatus.FAILED
    job.errorMessage = message
    job.completedAt = _utcnow()
    await session.commit()
