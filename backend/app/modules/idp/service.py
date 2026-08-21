"""Orquestração do módulo IDP/RSO. Porte de
`src/features/idp/services/index.ts` (`toIncrementalRecords`,
`recalcIdpIndicators`)."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.idp.calculations import compute_idp_result
from app.modules.idp.keys import idp_business_key, idp_content_hash
from app.modules.idp.repository import load_all_records, load_idp_configuration, reconstruct_records
from app.modules.idp.schemas import IdpRecordIn
from app.modules.idp.types import (
    IDP_DEFAULT_TARGET,
    IDP_INDICATOR,
    IDP_MODULE,
    IDP_UNIT_ALL,
    IdpAreaEntry,
    IdpExecutionPhase,
    IdpNormalizedRecord,
)
from app.shared.dates import parse_flex_date
from app.shared.incremental_upsert import IncrementalRecord

__all__ = ["recalc_idp_indicators", "to_incremental_records"]


def to_incremental_records(raw_records: list[Any]) -> tuple[list[IncrementalRecord], int]:
    """Revalida cada linha do lote (Zod "duas vezes" -> Pydantic aqui), gera
    `businessKey`/`contentHash` no servidor. Sem parsing de PDF aqui — o
    navegador já extraiu os campos; esta função só revalida o JSON."""
    records: list[IncrementalRecord] = []
    rejected = 0

    for raw in raw_records:
        try:
            parsed = IdpRecordIn.model_validate(raw)
        except ValidationError:
            rejected += 1
            continue

        period_start = parse_flex_date(parsed.period_start) if parsed.period_start else None
        period_end = parse_flex_date(parsed.period_end) if parsed.period_end else None
        emission_date = parse_flex_date(parsed.emission_date) if parsed.emission_date else None

        disc_data = {
            disciplina: [
                IdpAreaEntry(area=e.area, prev_acum=e.prev_acum, real_acum=e.real_acum) for e in entries
            ]
            for disciplina, entries in parsed.disc_data.items()
        }
        execucao_fases = [
            IdpExecutionPhase(label=p.label, prev_acum=p.prev_acum, real_acum=p.real_acum)
            for p in parsed.execucao_fases
        ]

        normalized = IdpNormalizedRecord(
            unit=parsed.unit,
            detected_unit=parsed.detected_unit,
            unit_adjusted=parsed.unit_adjusted,
            rso_numero=parsed.rso_numero,
            detected_rso_numero=parsed.detected_rso_numero,
            rso_adjusted=parsed.rso_adjusted,
            reference_year=parsed.reference_year,
            reference_month=parsed.reference_month,
            detected_reference_year=parsed.detected_reference_year,
            detected_reference_month=parsed.detected_reference_month,
            reference_source=parsed.reference_source,
            reference_original_text=parsed.reference_original_text,
            reference_adjusted=parsed.reference_adjusted,
            period_start=period_start,
            period_end=period_end,
            emission_date=emission_date,
            file_name=parsed.file_name,
            areas=list(parsed.areas),
            disc_data=disc_data,
            execucao_fases=execucao_fases,
            raw=parsed.raw,
        )

        business_key = idp_business_key(normalized)
        content_hash = idp_content_hash(normalized)
        records.append(
            IncrementalRecord(
                business_key=business_key,
                content_hash=content_hash,
                data={
                    "unit": normalized.unit,
                    "detectedUnit": normalized.detected_unit,
                    "unitAdjusted": normalized.unit_adjusted,
                    "rsoNumero": normalized.rso_numero,
                    "detectedRsoNumero": normalized.detected_rso_numero,
                    "rsoAdjusted": normalized.rso_adjusted,
                    "referenceYear": normalized.reference_year,
                    "referenceMonth": normalized.reference_month,
                    "detectedReferenceYear": normalized.detected_reference_year,
                    "detectedReferenceMonth": normalized.detected_reference_month,
                    "referenceSource": normalized.reference_source,
                    "referenceOriginalText": normalized.reference_original_text,
                    "referenceAdjusted": normalized.reference_adjusted,
                    "periodStart": period_start,
                    "periodEnd": period_end,
                    "emissionDate": emission_date,
                    "fileName": normalized.file_name,
                    "areas": normalized.areas,
                    "discData": {
                        disciplina: [
                            {"area": e.area, "prevAcum": e.prev_acum, "realAcum": e.real_acum}
                            for e in entries
                        ]
                        for disciplina, entries in disc_data.items()
                    },
                    "execucaoFases": [
                        {"label": p.label, "prevAcum": p.prev_acum, "realAcum": p.real_acum}
                        for p in execucao_fases
                    ],
                    "raw": normalized.raw,
                },
            )
        )

    return records, rejected


async def recalc_idp_indicators(session: AsyncSession) -> None:
    """Recalcula a COMPETÊNCIA MAIS RECENTE disponível (sem período travado)
    — apaga `IndicatorResult` do módulo/indicador e recria uma única linha
    se `active_documents > 0`. Disparado por: finalizar importação, hook de
    `PATCH /configuracoes` para as exclusões de disciplina/unidade, e
    `DELETE /idp/registros` por período."""
    from app.models.indicators import IndicatorResult

    rows = await load_all_records(session)
    pairs, _invalid = reconstruct_records(rows)
    records = [record for _row, record in pairs]
    configuration = await load_idp_configuration(session)

    result = compute_idp_result(
        records, IDP_DEFAULT_TARGET, configuration.excluded_disciplines, configuration.excluded_units
    )

    await session.execute(
        delete(IndicatorResult).where(
            IndicatorResult.module == IDP_MODULE, IndicatorResult.indicator == IDP_INDICATOR
        )
    )

    if result.active_documents > 0:
        included = [u for u in result.unit_rows if not u.excluded]
        adherence = result.aderencia_geral if result.aderencia_geral is not None else 0.0
        status = "OK" if adherence >= IDP_DEFAULT_TARGET else "ABAIXO"
        details = {
            "source": "RSO",
            "competence": f"{result.selected_year}-{result.selected_month:02d}",
            "activeDocuments": result.active_documents,
            "documents": [
                {"unit": u.unit, "rsoNumero": u.rso_numero, "fileName": u.file_name} for u in included
            ],
        }
        session.add(
            IndicatorResult(
                module=IDP_MODULE,
                indicator=IDP_INDICATOR,
                unit=IDP_UNIT_ALL,
                year=result.selected_year,
                month=result.selected_month,
                value=adherence,
                target=IDP_DEFAULT_TARGET,
                adherence=adherence,
                status=status,
                details=details,
            )
        )
    await session.flush()
