"""Acesso a dados do módulo RNC. Porte de
`src/features/rnc/repositories/index.ts`.

Contém o `RncDelegate` (implementa o protocolo `RecordDelegate` do motor de
importação incremental genérico, `app/shared/incremental_upsert.py`) e as
queries de apoio usadas pelas rotas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.common import utcnow
from app.models.imports import ImportJob, ImportStatus
from app.models.records import RncRecord
from app.models.settings import AppSetting
from app.modules.rnc.types import RNC_EXCLUDED_UNITS_SETTING_KEY, RNC_MODULE
from app.shared.incremental_upsert import IncrementalRecord

__all__ = [
    "RncConfiguration",
    "RncDelegate",
    "count_records",
    "load_all_records",
    "load_last_import",
    "load_rnc_configuration",
    "save_rnc_configuration",
]


@dataclass(slots=True)
class RncConfiguration:
    excluded_units: list[str]


class RncDelegate:
    """Implementa o protocolo `RecordDelegate` — usado tanto pelo motor de
    importação genérico (via `delegate_factory`) quanto diretamente em testes."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_business_key(self, business_key: str) -> str | None:
        result = await self._session.execute(
            select(RncRecord.contentHash).where(RncRecord.businessKey == business_key)
        )
        return result.scalar_one_or_none()

    async def insert(self, record: IncrementalRecord, import_id: str) -> None:
        data = record.data
        self._session.add(
            RncRecord(
                businessKey=record.business_key,
                contentHash=record.content_hash,
                statusRnc=data["statusRnc"],
                unidade=data["unidade"],
                dataCriacao=data["dataCriacao"],
                dataSolucao=data.get("dataSolucao"),
                tempoTratativa=data.get("tempoTratativa"),
                ofensor=data["ofensor"],
                year=data["year"],
                month=data["month"],
                raw=data["raw"],
                firstImportId=import_id,
                lastImportId=import_id,
            )
        )
        await self._session.flush()

    async def update(self, record: IncrementalRecord, import_id: str) -> None:
        """Só atualiza `contentHash`, `statusRnc`, `dataSolucao`,
        `tempoTratativa`, `raw`, `lastImportId` e `lastSeenAt` — `unidade`,
        `dataCriacao`, `ofensor`, `year`, `month` ficam travados no valor da
        primeira importação (compõem a `businessKey`)."""
        result = await self._session.execute(
            select(RncRecord).where(RncRecord.businessKey == record.business_key)
        )
        existing = result.scalar_one()
        data = record.data
        existing.contentHash = record.content_hash
        existing.statusRnc = data["statusRnc"]
        existing.dataSolucao = data.get("dataSolucao")
        existing.tempoTratativa = data.get("tempoTratativa")
        existing.raw = data["raw"]
        existing.lastImportId = import_id
        existing.lastSeenAt = utcnow()
        await self._session.flush()


async def load_all_records(session: AsyncSession) -> list[RncRecord]:
    """Sem filtro de período — usado por `recalc_rnc_indicators` e por
    GET/POST /publicacoes/rnc (o corte de período acontece dentro de
    `compute_rnc_result`, não na query)."""
    result = await session.execute(
        select(RncRecord).order_by(RncRecord.dataCriacao.asc(), RncRecord.unidade.asc())
    )
    return list(result.scalars().all())


async def count_records(session: AsyncSession, filters: list[Any]) -> int:
    stmt = select(func.count()).select_from(RncRecord)
    if filters:
        stmt = stmt.where(*filters)
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def load_last_import(session: AsyncSession) -> ImportJob | None:
    result = await session.execute(
        select(ImportJob)
        .where(
            ImportJob.module == RNC_MODULE,
            ImportJob.status.in_([ImportStatus.COMPLETED, ImportStatus.COMPLETED_WITH_ERRORS]),
        )
        .order_by(ImportJob.completedAt.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def load_rnc_configuration(session: AsyncSession) -> RncConfiguration:
    setting = await session.get(AppSetting, RNC_EXCLUDED_UNITS_SETTING_KEY)
    if setting is None or not isinstance(setting.value, list):
        return RncConfiguration(excluded_units=[])
    return RncConfiguration(excluded_units=[str(v) for v in setting.value])


async def save_rnc_configuration(session: AsyncSession, excluded_units: list[str]) -> None:
    setting = await session.get(AppSetting, RNC_EXCLUDED_UNITS_SETTING_KEY)
    if setting is None:
        session.add(AppSetting(key=RNC_EXCLUDED_UNITS_SETTING_KEY, value=list(excluded_units)))
    else:
        setting.value = list(excluded_units)
    await session.flush()
