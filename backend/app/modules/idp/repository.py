"""Acesso a dados do módulo IDP/RSO. Porte de
`src/features/idp/repositories/index.ts` + `src/features/idp/services/index.ts`
(`storedIdpRowToRecord`).

Contém o `IdpDelegate` (protocolo `RecordDelegate` do motor de importação
incremental) e a reidratação de linhas persistidas para `IdpNormalizedRecord`
— com uma correção mandatória em relação ao HEAD (ver
`docs/backend-migration-decisions.md` §4.2.4): uma linha corrompida não
derruba a rota inteira com 500, é ignorada e contada separadamente.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.common import utcnow
from app.models.imports import ImportJob, ImportStatus
from app.models.records import IdpRsoRecord
from app.models.settings import AppSetting
from app.modules.idp.types import (
    IDP_DEFAULT_EXCLUDED_DISCIPLINES,
    IDP_EXCLUDED_DISCIPLINES_SETTING_KEY,
    IDP_EXCLUDED_UNITS_SETTING_KEY,
    IDP_MODULE,
    IdpAreaEntry,
    IdpExecutionPhase,
    IdpNormalizedRecord,
)
from app.shared.incremental_upsert import IncrementalRecord

__all__ = [
    "IdpConfiguration",
    "IdpDelegate",
    "count_records",
    "load_all_records",
    "load_idp_configuration",
    "load_last_import",
    "reconstruct_records",
    "save_excluded_disciplines",
    "save_excluded_units",
    "stored_idp_row_to_record",
]

_logger = get_logger(__name__)


@dataclass(slots=True)
class IdpConfiguration:
    excluded_disciplines: list[str]
    excluded_units: list[str]


class IdpDelegate:
    """Implementa o protocolo `RecordDelegate` — usado tanto pelo motor de
    importação genérico (via `delegate_factory`) quanto diretamente em testes."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_business_key(self, business_key: str) -> str | None:
        result = await self._session.execute(
            select(IdpRsoRecord.contentHash).where(IdpRsoRecord.businessKey == business_key)
        )
        return result.scalar_one_or_none()

    async def insert(self, record: IncrementalRecord, import_id: str) -> None:
        data = record.data
        self._session.add(
            IdpRsoRecord(
                businessKey=record.business_key,
                contentHash=record.content_hash,
                unit=data["unit"],
                detectedUnit=data.get("detectedUnit"),
                unitAdjusted=data["unitAdjusted"],
                rsoNumero=data["rsoNumero"],
                detectedRsoNumero=data.get("detectedRsoNumero"),
                rsoAdjusted=data["rsoAdjusted"],
                referenceYear=data["referenceYear"],
                referenceMonth=data["referenceMonth"],
                detectedReferenceYear=data.get("detectedReferenceYear"),
                detectedReferenceMonth=data.get("detectedReferenceMonth"),
                referenceSource=data["referenceSource"],
                referenceOriginalText=data.get("referenceOriginalText"),
                referenceAdjusted=data["referenceAdjusted"],
                periodStart=data.get("periodStart"),
                periodEnd=data.get("periodEnd"),
                emissionDate=data.get("emissionDate"),
                fileName=data["fileName"],
                areas=data["areas"],
                discData=data["discData"],
                execucaoFases=data["execucaoFases"],
                raw=data["raw"],
                firstImportId=import_id,
                lastImportId=import_id,
            )
        )
        await self._session.flush()

    async def update(self, record: IncrementalRecord, import_id: str) -> None:
        """Atualiza todos os campos mutáveis (os que compõem o content
        hash) — `unitAdjusted`/`rsoAdjusted`/`detected*`/`referenceOriginalText`/
        `raw`/`fileName` também são atualizados aqui por conveniência (não
        entram no hash, mas não há razão para preservar valores obsoletos
        de auditoria quando uma correção real chega)."""
        result = await self._session.execute(
            select(IdpRsoRecord).where(IdpRsoRecord.businessKey == record.business_key)
        )
        existing = result.scalar_one()
        data = record.data
        existing.contentHash = record.content_hash
        existing.unit = data["unit"]
        existing.detectedUnit = data.get("detectedUnit")
        existing.unitAdjusted = data["unitAdjusted"]
        existing.rsoNumero = data["rsoNumero"]
        existing.detectedRsoNumero = data.get("detectedRsoNumero")
        existing.rsoAdjusted = data["rsoAdjusted"]
        existing.referenceYear = data["referenceYear"]
        existing.referenceMonth = data["referenceMonth"]
        existing.detectedReferenceYear = data.get("detectedReferenceYear")
        existing.detectedReferenceMonth = data.get("detectedReferenceMonth")
        existing.referenceSource = data["referenceSource"]
        existing.referenceOriginalText = data.get("referenceOriginalText")
        existing.referenceAdjusted = data["referenceAdjusted"]
        existing.periodStart = data.get("periodStart")
        existing.periodEnd = data.get("periodEnd")
        existing.emissionDate = data.get("emissionDate")
        existing.fileName = data["fileName"]
        existing.areas = data["areas"]
        existing.discData = data["discData"]
        existing.execucaoFases = data["execucaoFases"]
        existing.raw = data["raw"]
        existing.lastImportId = import_id
        existing.lastSeenAt = utcnow()
        await self._session.flush()


async def load_all_records(session: AsyncSession) -> list[IdpRsoRecord]:
    result = await session.execute(
        select(IdpRsoRecord).order_by(
            IdpRsoRecord.referenceYear.desc(),
            IdpRsoRecord.referenceMonth.desc(),
            IdpRsoRecord.unit.asc(),
            IdpRsoRecord.rsoNumero.desc(),
        )
    )
    return list(result.scalars().all())


async def count_records(session: AsyncSession, filters: list[Any]) -> int:
    stmt = select(func.count()).select_from(IdpRsoRecord)
    if filters:
        stmt = stmt.where(*filters)
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def load_last_import(session: AsyncSession) -> ImportJob | None:
    result = await session.execute(
        select(ImportJob)
        .where(
            ImportJob.module == IDP_MODULE,
            ImportJob.status.in_([ImportStatus.COMPLETED, ImportStatus.COMPLETED_WITH_ERRORS]),
        )
        .order_by(ImportJob.completedAt.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def load_idp_configuration(session: AsyncSession) -> IdpConfiguration:
    disciplines_setting = await session.get(AppSetting, IDP_EXCLUDED_DISCIPLINES_SETTING_KEY)
    if disciplines_setting is not None and isinstance(disciplines_setting.value, list):
        excluded_disciplines = [str(v) for v in disciplines_setting.value]
    else:
        excluded_disciplines = list(IDP_DEFAULT_EXCLUDED_DISCIPLINES)

    units_setting = await session.get(AppSetting, IDP_EXCLUDED_UNITS_SETTING_KEY)
    excluded_units = (
        [str(v) for v in units_setting.value]
        if units_setting is not None and isinstance(units_setting.value, list)
        else []
    )

    return IdpConfiguration(excluded_disciplines=excluded_disciplines, excluded_units=excluded_units)


async def save_excluded_disciplines(session: AsyncSession, values: list[str]) -> None:
    setting = await session.get(AppSetting, IDP_EXCLUDED_DISCIPLINES_SETTING_KEY)
    if setting is None:
        session.add(AppSetting(key=IDP_EXCLUDED_DISCIPLINES_SETTING_KEY, value=list(values)))
    else:
        setting.value = list(values)
    await session.flush()


async def save_excluded_units(session: AsyncSession, values: list[str]) -> None:
    setting = await session.get(AppSetting, IDP_EXCLUDED_UNITS_SETTING_KEY)
    if setting is None:
        session.add(AppSetting(key=IDP_EXCLUDED_UNITS_SETTING_KEY, value=list(values)))
    else:
        setting.value = list(values)
    await session.flush()


def _normalize_execution_phases(raw_phases: list[dict[str, Any]]) -> list[IdpExecutionPhase]:
    """Compatibilidade retroativa: `label` ausente/vazio (registros de uma
    versão anterior) vira `"Execução"` (fase única) ou `"Execução {n}"`
    (múltiplas fases) — nunca inventa `"Fase 1/2/3"` sem evidência do PDF."""
    n = len(raw_phases)
    phases: list[IdpExecutionPhase] = []
    for idx, p in enumerate(raw_phases):
        label = str(p.get("label") or "").strip()
        if not label:
            label = "Execução" if n == 1 else f"Execução {idx + 1}"
        phases.append(
            IdpExecutionPhase(label=label, prev_acum=float(p["prevAcum"]), real_acum=float(p["realAcum"]))
        )
    return phases


def stored_idp_row_to_record(row: IdpRsoRecord) -> IdpNormalizedRecord:
    """Reconstrói um `IdpNormalizedRecord` a partir de uma linha persistida.
    Pode lançar (`KeyError`/`TypeError`/`ValueError`) se os blobs JSON
    estiverem corrompidos — o chamador (`reconstruct_records`) captura por
    linha, nunca deixa uma linha ruim derrubar a rota inteira."""
    disc_data = {
        disciplina: [
            IdpAreaEntry(area=str(e["area"]), prev_acum=float(e["prevAcum"]), real_acum=float(e["realAcum"]))
            for e in entries
        ]
        for disciplina, entries in (row.discData or {}).items()
    }
    execucao_fases = _normalize_execution_phases(list(row.execucaoFases or []))
    reference_source = (
        row.referenceSource if row.referenceSource in ("PDF_MES_REF", "MANUAL") else "PDF_MES_REF"
    )

    return IdpNormalizedRecord(
        unit=row.unit,
        detected_unit=row.detectedUnit,
        unit_adjusted=row.unitAdjusted,
        rso_numero=row.rsoNumero,
        detected_rso_numero=row.detectedRsoNumero,
        rso_adjusted=row.rsoAdjusted,
        reference_year=row.referenceYear,
        reference_month=row.referenceMonth,
        detected_reference_year=row.detectedReferenceYear,
        detected_reference_month=row.detectedReferenceMonth,
        reference_source=reference_source,
        reference_original_text=row.referenceOriginalText,
        reference_adjusted=row.referenceAdjusted,
        period_start=row.periodStart,
        period_end=row.periodEnd,
        emission_date=row.emissionDate,
        file_name=row.fileName,
        areas=list(row.areas or []),
        disc_data=disc_data,
        execucao_fases=execucao_fases,
        raw=row.raw or {},
        id=row.id,
        updated_at=row.updatedAt,
    )


def reconstruct_records(
    rows: list[IdpRsoRecord],
) -> tuple[list[tuple[IdpRsoRecord, IdpNormalizedRecord]], int]:
    """Correção mandatória em relação ao HEAD (`storedIdpRowToRecord` sem
    try/catch por linha, `GET /api/idp` derrubava a rota inteira com 500 por
    UM registro corrompido — ver decisions.md §4.2.4). Retorna
    `(pares_linha_registro_validos, quantidade_ignorada)` — mantém a linha
    ORM original junto do registro normalizado porque alguns consumidores
    (rota `GET /idp`) precisam de colunas fora de `IdpNormalizedRecord`
    (`createdAt`, `firstImportId`, `lastImportId`)."""
    pairs: list[tuple[IdpRsoRecord, IdpNormalizedRecord]] = []
    invalid = 0
    for row in rows:
        try:
            pairs.append((row, stored_idp_row_to_record(row)))
        except (KeyError, TypeError, ValueError) as exc:
            invalid += 1
            _logger.warning(
                "idp.stored_record_invalid", record_id=row.id, unit=row.unit,
                rso_numero=row.rsoNumero, error=str(exc),
            )
    return pairs, invalid
