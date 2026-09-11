"""Orquestração do módulo RDO. Porte de `src/features/rdo/services/index.ts`.

Contém a revalidação server-side das importações (`to_incremental_records`),
a normalização da configuração de unidades excluídas, e o recálculo dos
`IndicatorResult` consolidados (`recalc_rdo_indicators`).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.records import RdoRecord
from app.modules.imports.bulk_upsert import bulk_upsert
from app.modules.imports.parsers.base import FileFormatError, FileParseResult
from app.modules.imports.parsers.rdo import dedupe_rdo_rows, parse_rdo_file, to_rdo_record
from app.modules.imports.registry import FileImportFileResult, FileImportOutcome, FileRowError
from app.modules.rdo.calculations import compute_rdo_result
from app.modules.rdo.keys import rdo_business_key, rdo_content_hash
from app.modules.rdo.repository import load_all_records, load_rdo_configuration
from app.modules.rdo.schemas import RdoRecordIn
from app.modules.rdo.types import RDO_DEFAULT_TARGET, RDO_INDICATOR, RDO_MODULE, RdoNormalizedRecord
from app.shared.dates import parse_flex_date
from app.shared.incremental_upsert import IncrementalRecord
from app.shared.units import normalize_unit_code

__all__ = [
    "normalize_excluded_units",
    "recalc_rdo_indicators",
    "run_rdo_file_import",
    "to_incremental_records",
]


def normalize_excluded_units(excluded_units: list[str]) -> list[str]:
    """`Array.from(new Set(values.map(normalizeRdoUnitCode).filter(Boolean)))`."""
    seen: list[str] = []
    for value in excluded_units:
        code = normalize_unit_code(value)
        if code and code not in seen:
            seen.append(code)
    return seen


def to_incremental_records(raw_records: list[Any]) -> tuple[list[IncrementalRecord], int]:
    """Revalida cada linha (Zod "duas vezes" -> Pydantic aqui), gera
    `businessKey`/`contentHash` no servidor. Linhas inválidas são descartadas
    silenciosamente e contadas em `rejected` (mesmo comportamento do TS)."""
    records: list[IncrementalRecord] = []
    rejected = 0

    for raw in raw_records:
        try:
            parsed = RdoRecordIn.model_validate(raw)
        except ValidationError:
            rejected += 1
            continue

        data_referencia = _parse_iso_datetime(parsed.data_referencia)
        if data_referencia is None:
            rejected += 1
            continue

        normalized = RdoNormalizedRecord(
            data_referencia=data_referencia,
            empresa_nome=parsed.empresa_nome,
            status_descricao=parsed.status_descricao,
            relatorio_id=parsed.relatorio_id,
            grupo=parsed.grupo,
            disciplina=parsed.disciplina,
            year=parsed.year,
            month=parsed.month,
            raw=parsed.raw,
        )

        business_key = rdo_business_key(normalized)
        content_hash = rdo_content_hash(normalized)
        records.append(
            IncrementalRecord(
                business_key=business_key,
                content_hash=content_hash,
                data={
                    "dataReferencia": data_referencia,
                    "empresaNome": normalized.empresa_nome,
                    "statusDescricao": normalized.status_descricao,
                    "relatorioId": normalized.relatorio_id,
                    "grupo": normalized.grupo,
                    "disciplina": normalized.disciplina,
                    "year": normalized.year,
                    "month": normalized.month,
                    "raw": normalized.raw,
                },
            )
        )

    return records, rejected


def _parse_iso_datetime(value: str) -> datetime | None:
    """O TS reparseia a string ISO já validada com `new Date(...)` — aqui
    aceitamos tanto ISO estrito quanto os formatos flexíveis de `parse_flex_date`
    (equivalente funcional, pois o Pydantic já garantiu que a string não é vazia)."""
    parsed = parse_flex_date(value)
    return parsed


async def recalc_rdo_indicators(session: AsyncSession) -> None:
    """Recalcula `IndicatorResult` para TODOS os (ano, mês) presentes na base
    inteira — sempre com `RDO_DEFAULT_TARGET` fixo (0.8), nunca o threshold de
    tela ou de publicação."""
    records = await load_all_records(session)
    configuration = await load_rdo_configuration(session)

    periods: set[tuple[int, int]] = {(r.year, r.month) for r in records}

    for year, month in periods:
        # `raw` não entra em `compute_rdo_result` — omitido de propósito
        # (`load_all_records` só carrega as colunas usadas aqui; ler `.raw`
        # dispararia um lazy-load coluna a coluna, uma query por registro).
        subset = [
            RdoNormalizedRecord(
                data_referencia=r.dataReferencia,
                empresa_nome=r.empresaNome,
                status_descricao=r.statusDescricao,
                relatorio_id=r.relatorioId,
                grupo=r.grupo,
                disciplina=r.disciplina,
                year=r.year,
                month=r.month,
            )
            for r in records
            if r.year == year and r.month == month
        ]
        result = compute_rdo_result(subset, RDO_DEFAULT_TARGET, configuration.excluded_units)
        adherence = (
            result.total_aprovados / result.total_emitidos if result.total_emitidos > 0 else 0.0
        )
        status = "OK" if adherence >= RDO_DEFAULT_TARGET else "ABAIXO"
        details = {
            "totalEmitidos": result.total_emitidos,
            "totalAprovados": result.total_aprovados,
            "totalRevisar": result.total_revisar,
            "totalPreenchendo": result.total_preenchendo,
            "unitAvg": result.unit_avg,
        }

        await _upsert_indicator_result(session, year, month, adherence, status, details)


async def _upsert_indicator_result(
    session: AsyncSession, year: int, month: int, adherence: float, status: str, details: dict[str, Any]
) -> None:
    from app.models.indicators import IndicatorResult

    stmt = pg_insert(IndicatorResult).values(
        module=RDO_MODULE,
        indicator=RDO_INDICATOR,
        unit="__ALL__",
        year=year,
        month=month,
        value=adherence,
        target=RDO_DEFAULT_TARGET,
        adherence=adherence,
        status=status,
        details=details,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["module", "indicator", "unit", "year", "month"],
        set_={
            "value": adherence,
            "target": RDO_DEFAULT_TARGET,
            "adherence": adherence,
            "status": status,
            "details": details,
        },
    )
    await session.execute(stmt)


_RDO_MUTABLE_COLUMNS = ("contentHash", "statusDescricao", "raw", "lastImportId")


def _build_rdo_insert_row(record: IncrementalRecord, import_id: str) -> dict[str, Any]:
    """Mesmas colunas que `RdoDelegate.insert` grava — reaproveitando o
    contrato já validado pelo fluxo linha-a-linha, só que agora numa única
    linha de um `VALUES` em lote."""
    data = record.data
    return {
        "businessKey": record.business_key,
        "contentHash": record.content_hash,
        "dataReferencia": data["dataReferencia"],
        "empresaNome": data["empresaNome"],
        "statusDescricao": data["statusDescricao"],
        "relatorioId": data.get("relatorioId"),
        "grupo": data.get("grupo"),
        "disciplina": data.get("disciplina"),
        "year": data["year"],
        "month": data["month"],
        "raw": data["raw"],
        "firstImportId": import_id,
        "lastImportId": import_id,
    }


async def _parse_rdo_file_safely(
    semaphore: asyncio.Semaphore, file_name: str, content: bytes
) -> FileParseResult:
    async with semaphore:
        try:
            return await asyncio.to_thread(parse_rdo_file, content, file_name)
        except FileFormatError as exc:
            result = FileParseResult(file_name=file_name)
            result.errors.append(FileRowError(row=None, field=None, message=str(exc)))
            return result


async def run_rdo_file_import(
    session: AsyncSession, files: list[tuple[str, bytes]], import_id: str
) -> FileImportOutcome:
    """Implementa `ModuleDefinition.file_import` do RDO para `POST
    /importacoes/rdo/arquivos`: parse de todos os arquivos (em thread,
    concorrência limitada), dedup entre arquivos, `to_incremental_records`
    (reaproveitado sem alteração — mesma validação/hash de sempre),
    `bulk_upsert` e `recalc_rdo_indicators` uma única vez. Tudo dentro da
    transação já aberta pelo chamador (`imports/service.py`)."""
    settings = get_settings()
    semaphore = asyncio.Semaphore(max(1, settings.import_file_concurrency))

    parsed = await asyncio.gather(
        *(_parse_rdo_file_safely(semaphore, name, content) for name, content in files)
    )

    max_rows = settings.max_import_rows_per_file
    for file_result in parsed:
        if file_result.found > max_rows:
            file_result.errors.append(
                FileRowError(
                    row=None, field=None,
                    message=f"Arquivo tem {file_result.found} linhas — limite de {max_rows} por arquivo.",
                )
            )
            file_result.rows = []

    all_rows: list[dict[str, Any]] = []
    for file_result in parsed:
        all_rows.extend(file_result.rows)

    deduped_rows, _duplicates = dedupe_rdo_rows(all_rows)

    # Rastreia, por linha deduplicada, a qual arquivo ela pertence (para
    # reportar erros de `to_incremental_records`/`to_rdo_record` no arquivo
    # certo). Como a dedup preserva a 1ª ocorrência, basta varrer os arquivos
    # na mesma ordem e "consumir" as linhas que sobraram por identidade.
    deduped_ids = {id(row) for row in deduped_rows}

    per_file: list[FileImportFileResult] = []
    raw_records: list[dict[str, Any]] = []
    row_origin: list[str] = []  # mesmo índice de `raw_records` -> nome do arquivo

    for file_result in parsed:
        accepted_in_file = 0
        file_errors = list(file_result.errors)
        for row in file_result.rows:
            if id(row) not in deduped_ids:
                continue
            converted = to_rdo_record(row)
            if converted is None:
                file_errors.append(
                    FileRowError(row=None, field="data", message="Linha sem data ou unidade válida.")
                )
                continue
            raw_records.append(converted)
            row_origin.append(file_result.file_name)
            accepted_in_file += 1
        per_file.append(
            FileImportFileResult(
                file_name=file_result.file_name,
                found=file_result.found,
                accepted=accepted_in_file,
                rejected=file_result.found - accepted_in_file,
                errors=file_errors,
            )
        )

    incremental_records, schema_rejected = to_incremental_records(raw_records)

    # `to_incremental_records` descarta silenciosamente linhas inválidas sem
    # dizer qual — distribui o total rejeitado proporcionalmente por arquivo
    # não é confiável; como cada `raw_records[i]` já passou por
    # `to_rdo_record` com sucesso, qualquer rejeição aqui vem de
    # `RdoRecordIn`/data inválida residual — soma no primeiro arquivo com
    # linhas para não perder a contagem no total do job.
    if schema_rejected and per_file:
        per_file[0].rejected += schema_rejected

    upsert_outcome = await bulk_upsert(
        session,
        RdoRecord,
        incremental_records,
        import_id=import_id,
        build_insert_row=_build_rdo_insert_row,
        mutable_columns=_RDO_MUTABLE_COLUMNS,
    )

    await recalc_rdo_indicators(session)

    return FileImportOutcome(
        inserted=upsert_outcome.inserted,
        updated=upsert_outcome.updated,
        ignored=upsert_outcome.ignored,
        rejected=sum(f.rejected for f in per_file),
        files=per_file,
    )
