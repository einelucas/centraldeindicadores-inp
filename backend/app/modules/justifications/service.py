"""Serviço de justificativas (CRUD genérico). Porte de
`src/app/api/justificativas/route.ts`."""

from __future__ import annotations

from datetime import UTC
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.models.indicators import IndicatorJustification
from app.models.user import User
from app.modules.justifications.schemas import EvidenceItem, SourceImportIn
from app.shared.audit import record_audit

JustificationRow = tuple[IndicatorJustification, User | None, User | None]


async def _attach_users(
    session: AsyncSession, records: list[IndicatorJustification]
) -> list[JustificationRow]:
    user_ids = {r.createdById for r in records} | {r.updatedById for r in records}
    users: dict[str, User] = {}
    if user_ids:
        result = await session.execute(select(User).where(User.id.in_(user_ids)))
        users = {u.id: u for u in result.scalars().all()}
    return [(r, users.get(r.createdById), users.get(r.updatedById)) for r in records]


async def list_justifications(
    session: AsyncSession, *, module: str, year: int, month: int | None = None
) -> list[JustificationRow]:
    stmt = select(IndicatorJustification).where(
        IndicatorJustification.module == module, IndicatorJustification.year == year
    )
    if month is not None:
        stmt = stmt.where(IndicatorJustification.month == month)
    stmt = stmt.order_by(
        IndicatorJustification.year.desc(),
        IndicatorJustification.month.desc(),
        IndicatorJustification.updatedAt.desc(),
    )
    result = await session.execute(stmt)
    return await _attach_users(session, list(result.scalars().all()))


async def _find_one(
    session: AsyncSession, *, module: str, year: int, month: int
) -> IndicatorJustification | None:
    stmt = select(IndicatorJustification).where(
        IndicatorJustification.module == module,
        IndicatorJustification.year == year,
        IndicatorJustification.month == month,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _snapshot(record: IndicatorJustification) -> dict[str, Any]:
    return {
        "id": record.id,
        "module": record.module,
        "year": record.year,
        "month": record.month,
        "result": record.result,
        "target": record.target,
        "status": record.status,
        "evidence": record.evidence,
        "suggestedText": record.suggestedText,
        "text": record.text,
        "sourceImportId": record.sourceImportId,
        "sourceImportedAt": record.sourceImportedAt.isoformat() if record.sourceImportedAt else None,
        "createdById": record.createdById,
        "updatedById": record.updatedById,
        "createdAt": record.createdAt.isoformat() if record.createdAt else None,
        "updatedAt": record.updatedAt.isoformat() if record.updatedAt else None,
    }


async def save_justification(
    session: AsyncSession,
    *,
    module: str,
    year: int,
    month: int,
    text: str,
    suggested_text: str | None,
    result: float | None,
    target: float | None,
    status: str | None,
    evidence: list[EvidenceItem],
    source_import: SourceImportIn | None,
    user: CurrentUser,
) -> IndicatorJustification:
    existing = await _find_one(session, module=module, year=year, month=month)
    previous_snapshot = _snapshot(existing) if existing is not None else None

    source_import_id = source_import.id if source_import is not None else None
    source_imported_at = source_import.imported_at if source_import is not None else None
    if source_imported_at is not None and source_imported_at.tzinfo is not None:
        source_imported_at = source_imported_at.astimezone(UTC).replace(tzinfo=None)

    common: dict[str, Any] = {
        "result": result,
        "target": target,
        "status": status,
        "evidence": [item.model_dump(exclude_none=True) for item in evidence],
        "suggestedText": suggested_text,
        "text": text,
        "sourceImportId": source_import_id,
        "sourceImportedAt": source_imported_at,
        "updatedById": user.id,
    }

    if existing is None:
        record = IndicatorJustification(module=module, year=year, month=month, createdById=user.id, **common)
        session.add(record)
    else:
        for field, value in common.items():
            setattr(existing, field, value)
        record = existing

    await session.flush()

    action = (
        "INDICATOR_JUSTIFICATION_UPDATED"
        if previous_snapshot is not None
        else "INDICATOR_JUSTIFICATION_CREATED"
    )
    await record_audit(
        session,
        user_id=user.id,
        action=action,
        entity="IndicatorJustification",
        entity_id=record.id,
        previous_data=previous_snapshot,
        new_data=_snapshot(record),
        metadata={"module": module, "year": year, "month": month},
    )
    await session.commit()
    await session.refresh(record)
    return record


async def delete_justification(
    session: AsyncSession, *, module: str, year: int, month: int, user: CurrentUser
) -> None:
    record = await _find_one(session, module=module, year=year, month=month)
    if record is None:
        return  # idempotente: sem erro quando o registro não existe

    previous_snapshot = _snapshot(record)
    record_id = record.id
    await session.delete(record)
    await session.flush()

    await record_audit(
        session,
        user_id=user.id,
        action="INDICATOR_JUSTIFICATION_DELETED",
        entity="IndicatorJustification",
        entity_id=record_id,
        previous_data=previous_snapshot,
        metadata={"module": module, "year": year, "month": month},
    )
    await session.commit()
