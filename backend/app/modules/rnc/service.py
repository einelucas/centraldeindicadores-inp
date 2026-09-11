"""Orquestração do módulo RNC. Porte de `src/features/rnc/services/index.ts`.

Contém a revalidação server-side das importações (`to_incremental_records`)
e o recálculo dos `IndicatorResult` consolidados (`recalc_rnc_indicators`).
"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.records import RncRecord
from app.modules.imports.bulk_upsert import bulk_upsert
from app.modules.imports.parsers.base import FileFormatError, FileParseResult
from app.modules.imports.parsers.rnc import dedupe_rnc_rows, parse_rnc_file, to_rnc_record
from app.modules.imports.registry import FileImportFileResult, FileImportOutcome, FileRowError
from app.modules.rnc.calculations import compute_rnc_result
from app.modules.rnc.keys import rnc_business_key, rnc_content_hash
from app.modules.rnc.repository import load_all_records, load_rnc_configuration
from app.modules.rnc.schemas import RncRecordIn
from app.modules.rnc.types import RNC_DEFAULT_MAX_DIAS, RNC_INDICATOR, RNC_MODULE, RncNormalizedRecord
from app.shared.dates import parse_flex_date
from app.shared.incremental_upsert import IncrementalRecord
from app.shared.units import normalize_unit_code

__all__ = [
    "normalize_excluded_units",
    "recalc_rnc_indicators",
    "run_rnc_file_import",
    "to_incremental_records",
]


def normalize_excluded_units(excluded_units: list[str]) -> list[str]:
    """`Array.from(new Set(values.map(normalizeRncUnitCode).filter(Boolean)))`."""
    seen: list[str] = []
    for value in excluded_units:
        code = normalize_unit_code(value)
        if code and code not in seen:
            seen.append(code)
    return seen


def to_incremental_records(raw_records: list[Any]) -> tuple[list[IncrementalRecord], int]:
    """Revalida cada linha (Zod "duas vezes" -> Pydantic aqui), gera
    `businessKey`/`contentHash` no servidor. Linhas inválidas, ou com
    `dataCriacao` não parseável, são descartadas silenciosamente e contadas
    em `rejected` (mesmo comportamento do TS: `rncRecordSchema.safeParse`
    falha, ou `new Date(input.dataCriacao)` é `NaN`).

    `dataSolucao`, quando presente mas não parseável, não rejeita a linha —
    apenas fica `None` (equivale a "ainda não solucionada"), decisão
    documentada em `docs/backend-migration-decisions.md` (não há um caminho
    de rejeição explícito para esse campo no TypeScript original)."""
    records: list[IncrementalRecord] = []
    rejected = 0

    for raw in raw_records:
        try:
            parsed = RncRecordIn.model_validate(raw)
        except ValidationError:
            rejected += 1
            continue

        data_criacao = parse_flex_date(parsed.data_criacao)
        if data_criacao is None:
            rejected += 1
            continue

        data_solucao = parse_flex_date(parsed.data_solucao) if parsed.data_solucao else None

        normalized = RncNormalizedRecord(
            status_rnc=parsed.status_rnc,
            unidade=parsed.unidade,
            data_criacao=data_criacao,
            data_solucao=data_solucao,
            tempo_tratativa=parsed.tempo_tratativa,
            ofensor=parsed.ofensor,
            year=parsed.year,
            month=parsed.month,
            raw=parsed.raw,
        )

        business_key = rnc_business_key(normalized)
        content_hash = rnc_content_hash(normalized)
        records.append(
            IncrementalRecord(
                business_key=business_key,
                content_hash=content_hash,
                data={
                    "statusRnc": normalized.status_rnc,
                    "unidade": normalized.unidade,
                    "dataCriacao": data_criacao,
                    "dataSolucao": data_solucao,
                    "tempoTratativa": normalized.tempo_tratativa,
                    "ofensor": normalized.ofensor,
                    "year": normalized.year,
                    "month": normalized.month,
                    "raw": normalized.raw,
                },
            )
        )

    return records, rejected


async def recalc_rnc_indicators(session: AsyncSession) -> None:
    """Recalcula `IndicatorResult` para TODOS os (ano, mês) presentes na base
    inteira — sempre com `RNC_DEFAULT_MAX_DIAS` fixo (15), nunca a meta de
    tela ou de publicação (Divergência #6 do inventário)."""
    records = await load_all_records(session)
    configuration = await load_rnc_configuration(session)

    normalized = [
        RncNormalizedRecord(
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
        for r in records
    ]
    result = compute_rnc_result(normalized, RNC_DEFAULT_MAX_DIAS, configuration.excluded_units)

    for month in result.months:
        dias = month.dias_medios
        adherence = (month.solucionados / month.chamados) if month.chamados else 0.0
        status = "SEM_DADOS" if dias is None else ("OK" if dias <= result.meta_dias else "ABAIXO")
        details = {
            "chamados": month.chamados,
            "solucionados": month.solucionados,
            "diasMedios": dias,
        }
        # +1: RncMonthAggregate.month é 0-based (Date.getMonth()); IndicatorResult.month é 1-based.
        await _upsert_indicator_result(session, month.year, month.month + 1, dias, status, adherence, details)


async def _upsert_indicator_result(
    session: AsyncSession,
    year: int,
    month: int,
    dias: float | None,
    status: str,
    adherence: float,
    details: dict[str, Any],
) -> None:
    from app.models.indicators import IndicatorResult

    value = dias if dias is not None else 0.0
    stmt = pg_insert(IndicatorResult).values(
        module=RNC_MODULE,
        indicator=RNC_INDICATOR,
        unit="__ALL__",
        year=year,
        month=month,
        value=value,
        target=RNC_DEFAULT_MAX_DIAS,
        adherence=adherence,
        status=status,
        details=details,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["module", "indicator", "unit", "year", "month"],
        set_={
            "value": value,
            "target": RNC_DEFAULT_MAX_DIAS,
            "adherence": adherence,
            "status": status,
            "details": details,
        },
    )
    await session.execute(stmt)


_RNC_MUTABLE_COLUMNS = (
    "contentHash",
    "statusRnc",
    "dataSolucao",
    "tempoTratativa",
    "raw",
    "lastImportId",
)


def _build_rnc_insert_row(record: IncrementalRecord, import_id: str) -> dict[str, Any]:
    data = record.data
    return {
        "businessKey": record.business_key,
        "contentHash": record.content_hash,
        "statusRnc": data["statusRnc"],
        "unidade": data["unidade"],
        "dataCriacao": data["dataCriacao"],
        "dataSolucao": data.get("dataSolucao"),
        "tempoTratativa": data.get("tempoTratativa"),
        "ofensor": data["ofensor"],
        "year": data["year"],
        "month": data["month"],
        "raw": data["raw"],
        "firstImportId": import_id,
        "lastImportId": import_id,
    }


async def _parse_rnc_file_safely(
    semaphore: asyncio.Semaphore, file_name: str, content: bytes
) -> FileParseResult:
    async with semaphore:
        try:
            return await asyncio.to_thread(parse_rnc_file, content, file_name)
        except FileFormatError as exc:
            result = FileParseResult(file_name=file_name)
            result.errors.append(FileRowError(row=None, field=None, message=str(exc)))
            return result


async def run_rnc_file_import(
    session: AsyncSession, files: list[tuple[str, bytes]], import_id: str
) -> FileImportOutcome:
    """Processa arquivos RNC dentro da transação controlada pelo importador."""
    settings = get_settings()
    semaphore = asyncio.Semaphore(max(1, settings.import_file_concurrency))
    parsed = await asyncio.gather(
        *(_parse_rnc_file_safely(semaphore, name, content) for name, content in files)
    )

    for file_result in parsed:
        if file_result.found > settings.max_import_rows_per_file:
            file_result.errors.append(
                FileRowError(
                    row=None,
                    field=None,
                    message=(
                        f"Arquivo tem {file_result.found} linhas — limite de "
                        f"{settings.max_import_rows_per_file} por arquivo."
                    ),
                )
            )
            file_result.rows = []

    all_rows = [row for file_result in parsed for row in file_result.rows]
    deduped_rows, _duplicates = dedupe_rnc_rows(all_rows)
    deduped_ids = {id(row) for row in deduped_rows}

    per_file: list[FileImportFileResult] = []
    raw_records: list[dict[str, Any]] = []
    for file_result in parsed:
        accepted = 0
        errors = list(file_result.errors)
        for row_index, row in enumerate(file_result.rows, start=2):
            if id(row) not in deduped_ids:
                continue
            converted = to_rnc_record(row)
            if converted is None:
                errors.append(
                    FileRowError(
                        row=row_index,
                        field="data_de_criacao",
                        message="Linha sem data de criação válida.",
                    )
                )
                continue
            raw_records.append(converted)
            accepted += 1
        per_file.append(
            FileImportFileResult(
                file_name=file_result.file_name,
                found=file_result.found,
                accepted=accepted,
                rejected=file_result.found - accepted,
                errors=errors,
            )
        )

    incremental_records, schema_rejected = to_incremental_records(raw_records)
    if schema_rejected and per_file:
        per_file[0].accepted = max(0, per_file[0].accepted - schema_rejected)
        per_file[0].rejected += schema_rejected

    upsert_outcome = await bulk_upsert(
        session,
        RncRecord,
        incremental_records,
        import_id=import_id,
        build_insert_row=_build_rnc_insert_row,
        mutable_columns=_RNC_MUTABLE_COLUMNS,
    )
    await recalc_rnc_indicators(session)

    return FileImportOutcome(
        inserted=upsert_outcome.inserted,
        updated=upsert_outcome.updated,
        ignored=upsert_outcome.ignored,
        rejected=sum(file.rejected for file in per_file),
        files=per_file,
    )
