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

from app.core.errors import DomainError, NotFoundError
from app.models.imports import ImportBatch, ImportFile, ImportJob, ImportStatus
from app.models.imports import ImportError as ImportErrorRow
from app.modules.imports.registry import DelegateFactory, FileImportOutcome, FileImportRunner
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


async def find_job_by_idempotency_key(
    session: AsyncSession, *, module: str, idempotency_key: str
) -> ImportJob | None:
    result = await session.execute(
        select(ImportJob).where(ImportJob.module == module, ImportJob.idempotencyKey == idempotency_key)
    )
    return result.scalar_one_or_none()


async def run_file_import(
    session: AsyncSession,
    *,
    module: str,
    files: list[tuple[str, bytes]],
    user_id: str,
    idempotency_key: str | None,
    file_import: FileImportRunner,
) -> tuple[ImportJob, FileImportOutcome]:
    """Orquestra `POST /importacoes/{modulo}/arquivos` de ponta a ponta.

    Duas transações, de propósito (mesmo espírito de `start_import_job` +
    `finalize_import_job` já separados no fluxo antigo):
    1. Cria o `ImportJob` (status `PROCESSING`) e comita imediatamente — é o
       que faz a chave de idempotência valer mesmo sob corrida concorrente
       (índice único `(module, idempotencyKey)`; uma segunda tentativa com a
       mesma chave "perde a corrida" e cai no `IntegrityError` abaixo).
    2. Roda `file_import` (parse + dedup + upsert em lote + recálculo do
       indicador, tudo do módulo) na mesma sessão, grava o histórico por
       arquivo/erro, atualiza os totais do job e comita tudo junto — se
       qualquer parte falhar, `rollback()` desfaz o upsert/recálculo inteiro
       (atomicidade), e o job (já commitado na etapa 1) é marcado `FAILED`
       numa transação separada.
    """
    if idempotency_key:
        existing = await find_job_by_idempotency_key(session, module=module, idempotency_key=idempotency_key)
        if existing is not None and existing.status in (
            ImportStatus.COMPLETED,
            ImportStatus.COMPLETED_WITH_ERRORS,
        ):
            outcome = FileImportOutcome(
                inserted=existing.totalInserted,
                updated=existing.totalUpdated,
                ignored=existing.totalIgnored,
                rejected=existing.totalRejected,
                files=[],
            )
            return existing, outcome

    job = ImportJob(
        module=module,
        fileName=", ".join(name for name, _content in files)[:300],
        totalFound=0,
        status=ImportStatus.PROCESSING,
        userId=user_id,
        idempotencyKey=idempotency_key,
    )
    session.add(job)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if idempotency_key:
            existing = await find_job_by_idempotency_key(
                session, module=module, idempotency_key=idempotency_key
            )
            if existing is not None:
                outcome = FileImportOutcome(
                    inserted=existing.totalInserted,
                    updated=existing.totalUpdated,
                    ignored=existing.totalIgnored,
                    rejected=existing.totalRejected,
                    files=[],
                )
                return existing, outcome
        raise DomainError("Não foi possível iniciar a importação.") from exc

    await record_audit(
        session,
        user_id=user_id,
        action="IMPORT_STARTED",
        entity="ImportJob",
        entity_id=job.id,
        metadata={"module": module, "fileNames": [name for name, _content in files]},
    )
    await session.commit()
    await session.refresh(job)

    try:
        outcome = await file_import(session, files, job.id)

        for file_result in outcome.files:
            session.add(
                ImportFile(
                    importJobId=job.id,
                    fileName=file_result.file_name,
                    found=file_result.found,
                    accepted=file_result.accepted,
                    rejected=file_result.rejected,
                )
            )
            for error in file_result.errors:
                session.add(
                    ImportErrorRow(
                        importJobId=job.id,
                        fileName=file_result.file_name,
                        rowNumber=error.row,
                        field=error.field,
                        message=error.message,
                    )
                )

        job.totalFound = sum(f.found for f in outcome.files)
        job.totalInserted = outcome.inserted
        job.totalUpdated = outcome.updated
        job.totalIgnored = outcome.ignored
        job.totalRejected = outcome.rejected
        job.status = ImportStatus.COMPLETED_WITH_ERRORS if outcome.rejected > 0 else ImportStatus.COMPLETED
        job.completedAt = _utcnow()

        await record_audit(
            session,
            user_id=user_id,
            action="IMPORT_COMPLETED",
            entity="ImportJob",
            entity_id=job.id,
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
    except Exception as exc:  # noqa: BLE001 — precisa capturar qualquer falha para garantir rollback + FAILED
        await session.rollback()
        await fail_import_job(session, job.id, str(exc))
        raise

    return job, outcome
