"""Acesso a dados do módulo RDO. Porte de
`src/features/rdo/repositories/index.ts`.

Contém o `RdoDelegate` (implementa o protocolo `RecordDelegate` do motor de
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
from app.models.records import RdoRecord
from app.models.settings import AppSetting
from app.modules.rdo.types import RDO_EXCLUDED_UNITS_SETTING_KEY, RDO_MODULE
from app.shared.incremental_upsert import IncrementalRecord

__all__ = [
    "RdoConfiguration",
    "RdoDelegate",
    "count_records",
    "load_all_records",
    "load_calculation_rows",
    "load_detail_rows",
    "load_filter_options",
    "load_last_import",
    "load_rdo_configuration",
    "save_rdo_configuration",
]


@dataclass(slots=True)
class RdoConfiguration:
    excluded_units: list[str]


class RdoDelegate:
    """Implementa o protocolo `RecordDelegate` — usado tanto pelo motor de
    importação genérico (via `delegate_factory`) quanto diretamente em testes."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_business_key(self, business_key: str) -> str | None:
        result = await self._session.execute(
            select(RdoRecord.contentHash).where(RdoRecord.businessKey == business_key)
        )
        return result.scalar_one_or_none()

    async def insert(self, record: IncrementalRecord, import_id: str) -> None:
        data = record.data
        self._session.add(
            RdoRecord(
                businessKey=record.business_key,
                contentHash=record.content_hash,
                dataReferencia=data["dataReferencia"],
                empresaNome=data["empresaNome"],
                statusDescricao=data["statusDescricao"],
                relatorioId=data.get("relatorioId"),
                grupo=data.get("grupo"),
                disciplina=data.get("disciplina"),
                year=data["year"],
                month=data["month"],
                raw=data["raw"],
                firstImportId=import_id,
                lastImportId=import_id,
            )
        )
        await self._session.flush()

    async def update(self, record: IncrementalRecord, import_id: str) -> None:
        """Só atualiza `contentHash`, `statusDescricao`, `raw`, `lastImportId`
        e `lastSeenAt` — o restante é tratado como identidade imutável (compõe
        a `businessKey`)."""
        result = await self._session.execute(
            select(RdoRecord).where(RdoRecord.businessKey == record.business_key)
        )
        existing = result.scalar_one()
        existing.contentHash = record.content_hash
        existing.statusDescricao = record.data["statusDescricao"]
        existing.raw = record.data["raw"]
        existing.lastImportId = import_id
        existing.lastSeenAt = utcnow()
        await self._session.flush()


async def load_all_records(session: AsyncSession) -> list[RdoRecord]:
    """Sem filtro — usado por `recalc_rdo_indicators` e por POST /publicacoes/rdo."""
    result = await session.execute(
        select(RdoRecord).order_by(RdoRecord.dataReferencia.asc(), RdoRecord.empresaNome.asc())
    )
    return list(result.scalars().all())


async def load_calculation_rows(session: AsyncSession, filters: list[Any]) -> list[RdoRecord]:
    stmt = select(RdoRecord).order_by(RdoRecord.dataReferencia.asc(), RdoRecord.empresaNome.asc())
    if filters:
        stmt = stmt.where(*filters)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def load_detail_rows(
    session: AsyncSession, filters: list[Any], limit: int = 1000
) -> list[RdoRecord]:
    stmt = (
        select(RdoRecord)
        .order_by(RdoRecord.dataReferencia.desc(), RdoRecord.empresaNome.asc())
        .limit(limit)
    )
    if filters:
        stmt = stmt.where(*filters)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_records(session: AsyncSession, filters: list[Any]) -> int:
    stmt = select(func.count()).select_from(RdoRecord)
    if filters:
        stmt = stmt.where(*filters)
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def load_filter_options(session: AsyncSession) -> list[tuple[str, int, str]]:
    """Opções de filtro vêm da base inteira, sem `where` (mesmo com filtros
    ativos na tela principal)."""
    result = await session.execute(
        select(RdoRecord.empresaNome, RdoRecord.year, RdoRecord.statusDescricao).distinct()
    )
    return [(row[0], row[1], row[2]) for row in result.all()]


async def load_last_import(session: AsyncSession) -> ImportJob | None:
    result = await session.execute(
        select(ImportJob)
        .where(
            ImportJob.module == RDO_MODULE,
            ImportJob.status.in_([ImportStatus.COMPLETED, ImportStatus.COMPLETED_WITH_ERRORS]),
        )
        .order_by(ImportJob.completedAt.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def load_rdo_configuration(session: AsyncSession) -> RdoConfiguration:
    setting = await session.get(AppSetting, RDO_EXCLUDED_UNITS_SETTING_KEY)
    if setting is None or not isinstance(setting.value, list):
        return RdoConfiguration(excluded_units=[])
    return RdoConfiguration(excluded_units=[str(v) for v in setting.value])


async def save_rdo_configuration(session: AsyncSession, excluded_units: list[str]) -> None:
    setting = await session.get(AppSetting, RDO_EXCLUDED_UNITS_SETTING_KEY)
    if setting is None:
        session.add(AppSetting(key=RDO_EXCLUDED_UNITS_SETTING_KEY, value=list(excluded_units)))
    else:
        setting.value = list(excluded_units)
    await session.flush()
