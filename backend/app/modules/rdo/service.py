"""Orquestração do módulo RDO. Porte de `src/features/rdo/services/index.ts`.

Contém a revalidação server-side das importações (`to_incremental_records`),
a normalização da configuração de unidades excluídas, e o recálculo dos
`IndicatorResult` consolidados (`recalc_rdo_indicators`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.rdo.calculations import compute_rdo_result
from app.modules.rdo.keys import rdo_business_key, rdo_content_hash
from app.modules.rdo.repository import load_all_records, load_rdo_configuration
from app.modules.rdo.schemas import RdoRecordIn
from app.modules.rdo.types import RDO_DEFAULT_TARGET, RDO_INDICATOR, RDO_MODULE, RdoNormalizedRecord
from app.shared.dates import parse_flex_date
from app.shared.incremental_upsert import IncrementalRecord
from app.shared.units import normalize_unit_code

__all__ = ["normalize_excluded_units", "recalc_rdo_indicators", "to_incremental_records"]


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
                raw=r.raw,
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
