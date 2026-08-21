"""Orquestração do módulo 5S. Porte de `src/features/cinco-s/services/index.ts`.

Revalidação server-side das importações (`to_incremental_records`) e
recálculo dos `IndicatorResult` consolidados (`recalc_five_s_indicators`).
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cinco_s.calculations import compute_five_s_result
from app.modules.cinco_s.keys import five_s_business_key, five_s_content_hash
from app.modules.cinco_s.repository import (
    list_five_s_records,
    load_five_s_configuration,
    record_from_row,
    replace_indicator_results,
)
from app.modules.cinco_s.schemas import FiveSRecordIn
from app.modules.cinco_s.types import INDICATOR_NAME, MODULE_NAME, FiveSArea, FiveSNormalizedRecord
from app.shared.incremental_upsert import IncrementalRecord

__all__ = ["recalc_five_s_indicators", "to_incremental_records"]


def to_incremental_records(raw_records: list[Any]) -> tuple[list[IncrementalRecord], int]:
    records: list[IncrementalRecord] = []
    rejected = 0

    for raw in raw_records:
        try:
            parsed = FiveSRecordIn.model_validate(raw)
        except ValidationError:
            rejected += 1
            continue

        areas = [
            FiveSArea(divisao=area.divisao, area=area.area, meta=area.meta, nota=area.nota)
            for area in parsed.areas
        ]
        normalized = FiveSNormalizedRecord(
            unit=parsed.unit, year=parsed.year, month=parsed.month, areas=areas, raw=parsed.raw
        )

        business_key = five_s_business_key(normalized)
        content_hash = five_s_content_hash(normalized)
        records.append(
            IncrementalRecord(
                business_key=business_key,
                content_hash=content_hash,
                data={
                    "unit": normalized.unit,
                    "year": normalized.year,
                    "month": normalized.month,
                    "areas": areas,
                    "raw": {k: v for k, v in normalized.raw.items() if k != "areas"},
                },
            )
        )

    return records, rejected


async def recalc_five_s_indicators(session: AsyncSession) -> None:
    """Recalcula `IndicatorResult` para todo mês real com `geral` não nulo —
    mesma semântica de `recalcFiveSIndicators` (deleteMany + create)."""
    rows = await list_five_s_records(session)
    records = [record_from_row(row) for row in rows]
    threshold, excluded_units = await load_five_s_configuration(session)

    result = compute_five_s_result(records, excluded_units, threshold)

    indicator_rows: list[dict[str, Any]] = []
    for month in result.months:
        if month.geral is None:
            continue
        status = "OK" if month.geral >= threshold else "ABAIXO"
        indicator_rows.append(
            {
                "module": MODULE_NAME,
                "indicator": INDICATOR_NAME,
                "unit": "__ALL__",
                "year": month.year,
                "month": month.month,
                "value": month.geral,
                "target": threshold,
                "adherence": month.geral,
                "status": status,
                "details": {"unitsCount": month.units_count},
            }
        )

    await replace_indicator_results(session, rows=indicator_rows)
