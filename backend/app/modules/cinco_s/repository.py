"""Repositório do 5S: `FiveSDelegate` (motor incremental genérico), consultas
e persistência de `FiveSRecord`/`IndicatorResult`/`IndicatorPublication`, e
configurações (`fiveS.target`/`fiveS.excludedUnits`) especificamente para o
caminho `/cinco-s`.

Porte de `src/features/cinco-s/repositories/index.ts` +
as partes de leitura/escrita de `AppSetting` de
`src/features/cinco-s/services/index.ts` (`loadFiveSConfiguration`) usadas
por este caminho.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.common import utcnow
from app.models.imports import ImportJob, ImportStatus
from app.models.indicators import IndicatorPublication, IndicatorResult
from app.models.records import FiveSRecord
from app.models.settings import AppSetting
from app.modules.cinco_s.types import (
    FIVE_S_DEFAULT_EXCLUDED,
    FIVE_S_DEFAULT_TARGET,
    FIVES_EXCLUDED_SETTING,
    FIVES_TARGET_SETTING,
    INDICATOR_NAME,
    MODULE_NAME,
    FiveSArea,
    FiveSNormalizedRecord,
)
from app.shared.incremental_upsert import IncrementalRecord
from app.shared.period import PeriodRange, period_range_predicate
from app.shared.publication_cycle import PublicationCycle
from app.shared.units import normalize_unit_code


def normalize_excluded_units(values: list[str]) -> list[str]:
    """Normaliza cada item via `normalize_unit_code`, remove vazios e faz
    dedup preservando a ordem de primeira ocorrência."""
    seen: dict[str, None] = {}
    for value in values:
        code = normalize_unit_code(value)
        if code:
            seen.setdefault(code, None)
    return list(seen)


def record_from_row(row: FiveSRecord) -> FiveSNormalizedRecord:
    """Reconstrói um `FiveSNormalizedRecord` a partir de uma linha
    persistida — `areas` vem de `raw.areas` (fundido no insert/update)."""
    raw = dict(row.raw or {})
    areas_raw = raw.get("areas") or []
    areas = [
        FiveSArea(
            divisao=item.get("divisao"),
            area=item.get("area", ""),
            meta=float(item.get("meta", 0)),
            nota=float(item.get("nota", 0)),
        )
        for item in areas_raw
    ]
    return FiveSNormalizedRecord(unit=row.unit, year=row.year, month=row.month, areas=areas, raw=raw)


async def list_five_s_records(session: AsyncSession) -> list[FiveSRecord]:
    result = await session.execute(
        select(FiveSRecord).order_by(FiveSRecord.year, FiveSRecord.month, FiveSRecord.unit)
    )
    return list(result.scalars().all())


async def count_five_s_records(session: AsyncSession, period: PeriodRange | None) -> int:
    stmt = select(func.count()).select_from(FiveSRecord)
    if period is not None:
        stmt = stmt.where(period_range_predicate(period, FiveSRecord.year, FiveSRecord.month))
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def delete_all_five_s_records(session: AsyncSession) -> None:
    await session.execute(delete(FiveSRecord))
    await session.flush()


async def delete_five_s_records_in_period(session: AsyncSession, period: PeriodRange) -> None:
    await session.execute(
        delete(FiveSRecord).where(period_range_predicate(period, FiveSRecord.year, FiveSRecord.month))
    )
    await session.flush()


async def get_last_import(session: AsyncSession) -> ImportJob | None:
    result = await session.execute(
        select(ImportJob)
        .where(
            ImportJob.module == MODULE_NAME,
            ImportJob.status.in_([ImportStatus.COMPLETED, ImportStatus.COMPLETED_WITH_ERRORS]),
        )
        .order_by(ImportJob.completedAt.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def load_five_s_configuration(session: AsyncSession) -> tuple[float, list[str]]:
    """Lê `fiveS.target`/`fiveS.excludedUnits` de `AppSetting`, com defaults
    (`0.9` / `["SP","CSC"]`) quando ausentes ou fora do formato/faixa
    esperados (target deve ser um número finito em [0,1])."""
    result = await session.execute(
        select(AppSetting).where(AppSetting.key.in_([FIVES_TARGET_SETTING, FIVES_EXCLUDED_SETTING]))
    )
    by_key: dict[str, Any] = {row.key: row.value for row in result.scalars().all()}

    threshold = FIVE_S_DEFAULT_TARGET
    target_value = by_key.get(FIVES_TARGET_SETTING)
    if isinstance(target_value, int | float) and not isinstance(target_value, bool):
        numeric = float(target_value)
        if numeric == numeric and abs(numeric) != float("inf") and 0 <= numeric <= 1:  # isfinite inline
            threshold = numeric

    excluded_value = by_key.get(FIVES_EXCLUDED_SETTING)
    if isinstance(excluded_value, list):
        excluded_units = normalize_excluded_units([str(item) for item in excluded_value])
    else:
        excluded_units = list(FIVE_S_DEFAULT_EXCLUDED)

    return threshold, excluded_units


async def save_five_s_settings(session: AsyncSession, *, threshold: float, excluded_units: list[str]) -> None:
    """Upsert de `fiveS.target`/`fiveS.excludedUnits`. Usado pelos dois
    caminhos de escrita do módulo (`PATCH /cinco-s` e `POST
    /publicacoes/cinco-s`) — NÃO usado pelo caminho genérico
    `/configuracoes` (fora deste módulo)."""
    for setting_key, setting_value in (
        (FIVES_TARGET_SETTING, threshold),
        (FIVES_EXCLUDED_SETTING, excluded_units),
    ):
        stmt = (
            pg_insert(AppSetting)
            .values(key=setting_key, value=setting_value, updatedAt=utcnow())
            .on_conflict_do_update(
                index_elements=["key"], set_={"value": setting_value, "updatedAt": utcnow()}
            )
        )
        await session.execute(stmt)
    await session.flush()


async def replace_indicator_results(session: AsyncSession, *, rows: list[dict[str, Any]]) -> None:
    """Apaga todos os `IndicatorResult` do módulo 5S e recria a partir de
    `rows` — mesma semântica de `recalcFiveSIndicators` (deleteMany + create
    por mês real com `geral` não nulo)."""
    await session.execute(delete(IndicatorResult).where(IndicatorResult.module == MODULE_NAME))
    for row in rows:
        session.add(IndicatorResult(**row))
    await session.flush()


async def delete_all_indicator_results(session: AsyncSession) -> None:
    await session.execute(delete(IndicatorResult).where(IndicatorResult.module == MODULE_NAME))
    await session.flush()


async def get_latest_publication_version(session: AsyncSession) -> int | None:
    result = await session.execute(
        select(IndicatorPublication.version)
        .where(IndicatorPublication.module == MODULE_NAME, IndicatorPublication.indicator == INDICATOR_NAME)
        .order_by(IndicatorPublication.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def deactivate_publications(session: AsyncSession, *, cycle: PublicationCycle | None) -> None:
    """Desativa publicações ativas antes de criar uma nova. Se `cycle` for
    resolvido (período bate exatamente com um semestre operacional inteiro),
    desativa só as ativas do mesmo ciclo — permite publicações ativas
    simultâneas de ciclos diferentes. Senão, desativa TODAS as ativas do
    módulo (comportamento assimétrico preservado de propósito)."""
    stmt = update(IndicatorPublication).where(
        IndicatorPublication.module == MODULE_NAME,
        IndicatorPublication.indicator == INDICATOR_NAME,
        IndicatorPublication.active.is_(True),
    )
    if cycle is not None:
        stmt = stmt.where(
            IndicatorPublication.cycleYear == cycle.year,
            IndicatorPublication.cycleSemester == cycle.semester.value,
        )
    await session.execute(stmt.values(active=False))
    await session.flush()


class FiveSDelegate:
    """Implementa o `RecordDelegate` (Protocol) do motor incremental
    genérico (`app.shared.incremental_upsert`) para o 5S."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_business_key(self, business_key: str) -> str | None:
        result = await self._session.execute(
            select(FiveSRecord.contentHash).where(FiveSRecord.businessKey == business_key)
        )
        return result.scalar_one_or_none()

    async def insert(self, record: IncrementalRecord, import_id: str) -> None:
        data = record.data
        areas: list[FiveSArea] = data["areas"]
        raw = {**data.get("raw", {}), "areas": [asdict(area) for area in areas]}
        self._session.add(
            FiveSRecord(
                businessKey=record.business_key,
                contentHash=record.content_hash,
                unit=data["unit"],
                year=data["year"],
                month=data["month"],
                aderencia=_aderencia_unidade(areas),
                areasCount=len(areas),
                raw=raw,
                firstImportId=import_id,
                lastImportId=import_id,
            )
        )
        await self._session.flush()

    async def update(self, record: IncrementalRecord, import_id: str) -> None:
        data = record.data
        areas: list[FiveSArea] = data["areas"]
        raw = {**data.get("raw", {}), "areas": [asdict(area) for area in areas]}
        result = await self._session.execute(
            select(FiveSRecord).where(FiveSRecord.businessKey == record.business_key)
        )
        row = result.scalar_one()
        row.contentHash = record.content_hash
        row.aderencia = _aderencia_unidade(areas)
        row.areasCount = len(areas)
        row.raw = raw
        row.lastImportId = import_id
        row.lastSeenAt = utcnow()
        await self._session.flush()


def _aderencia_unidade(areas: list[FiveSArea]) -> float:
    # Import tardio para evitar ciclo (calculations.py não depende de repository.py).
    from app.modules.cinco_s.calculations import aderencia_unidade

    return aderencia_unidade(areas)
