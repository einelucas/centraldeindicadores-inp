"""Orquestração do Scorecard — junta publicações + snapshots salvos e monta
os contratos de resposta HTTP. Regra de negócio pura vive em `calculations.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scorecard import repository
from app.modules.scorecard.calculations import (
    ScorecardResult,
    compute_scorecard,
    latest_published_value_for_period,
    merge_live_with_saved_fallback,
    read_snapshot_values,
)
from app.modules.scorecard.types import SC_INDICATORS
from app.shared.period import PeriodRange, get_current_cycle


@dataclass(slots=True)
class ScorecardComputation:
    year: int
    month: int
    source_values: dict[str, float | None]
    values: dict[str, float | None]
    result: ScorecardResult


async def _live_values_for_month(
    session: AsyncSession, year: int, month: int
) -> dict[str, float | None]:
    """Para cada indicador, usa `latest_published_value_for_period` — varre o
    HISTÓRICO de publicações daquele módulo/indicador (não só a versão ativa)
    até achar um valor para o mês pedido. Implementa "recuperação de valor
    mensal em uma publicação anterior quando a mais recente não contém aquele
    mês"."""
    all_publications = await repository.list_all_source_publications(session)
    live_values: dict[str, float | None] = {}
    for indicator in SC_INDICATORS:
        if indicator.source is None:
            live_values[indicator.key] = None
            continue
        matching = [
            p
            for p in all_publications
            if p.module == indicator.source.module and p.indicator == indicator.source.indicator
        ]
        live_values[indicator.key] = latest_published_value_for_period(
            indicator.key, matching, year, month  # type: ignore[arg-type]
        )
    return live_values


async def compute_scorecard_for_month(session: AsyncSession, year: int, month: int) -> ScorecardComputation:
    live_values = await _live_values_for_month(session, year, month)
    snapshot = await repository.get_scorecard_snapshot(session, year, month)
    saved_values = read_snapshot_values(snapshot.raw) if snapshot is not None else None

    merged = merge_live_with_saved_fallback(live_values, saved_values)
    result = compute_scorecard(merged)

    return ScorecardComputation(
        year=year, month=month, source_values=live_values, values=merged, result=result
    )


async def save_scorecard_snapshot(
    session: AsyncSession, *, year: int, month: int, overrides: dict[str, float | None] | None = None
) -> ScorecardComputation:
    """"Salvar snapshot" grava os valores AO VIVO do momento do clique — não é
    edição manual (ver docs/scorecard-2026.md). `overrides` só participa como
    respaldo para um indicador SEM valor ao vivo E sem snapshot anterior —
    nunca substitui um valor ao vivo existente, preservando a regra "ao vivo
    sempre vence"."""
    live_values = await _live_values_for_month(session, year, month)
    existing_snapshot = await repository.get_scorecard_snapshot(session, year, month)
    previous_saved = read_snapshot_values(existing_snapshot.raw) if existing_snapshot is not None else None

    to_save: dict[str, float | None] = {}
    overrides = overrides or {}
    for indicator in SC_INDICATORS:
        live = live_values.get(indicator.key)
        if live is not None:
            to_save[indicator.key] = live
        elif previous_saved is not None and previous_saved.get(indicator.key) is not None:
            to_save[indicator.key] = previous_saved[indicator.key]
        else:
            to_save[indicator.key] = overrides.get(indicator.key)

    await repository.save_scorecard_snapshot(session, year=year, month=month, values=to_save)

    merged = merge_live_with_saved_fallback(live_values, to_save)
    result = compute_scorecard(merged)
    return ScorecardComputation(
        year=year, month=month, source_values=live_values, values=merged, result=result
    )


@dataclass(slots=True)
class HistoryItem:
    year: int
    month: int
    values: dict[str, float | None]
    result: ScorecardResult


async def list_scorecard_history(
    session: AsyncSession, period: PeriodRange | None
) -> list[HistoryItem]:
    resolved_period = period or get_current_cycle()
    snapshots = await repository.list_scorecard_snapshots(session, resolved_period)
    items: list[HistoryItem] = []
    for snapshot in snapshots:
        values = read_snapshot_values(snapshot.raw)
        items.append(
            HistoryItem(
                year=snapshot.year, month=snapshot.month, values=values, result=compute_scorecard(values)
            )
        )
    return items


async def delete_scorecard_history(session: AsyncSession, period: PeriodRange) -> int:
    return await repository.delete_scorecard_snapshots_in_period(session, period)


async def get_panel_period(session: AsyncSession) -> PeriodRange | None:
    return await repository.get_panel_period(session)


async def save_panel_period(session: AsyncSession, period: PeriodRange) -> None:
    await repository.save_panel_period(session, period)
