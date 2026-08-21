"""Serviço de indicadores consolidados. Porte de
`src/app/api/indicadores/route.ts`.

Leitura pura da tabela agregada/materializada `IndicatorResult` — não
recalcula nada; apenas lê o que os `recalc_indicators` de cada módulo já
gravaram (cada módulo é responsável por manter `IndicatorResult` atualizado
nas suas próprias rotas, fora do escopo deste pacote genérico).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.indicators import IndicatorResult

# Mesmos 6 módulos de `ACTIVE_INDICATOR_MODULES` no TS original. Inclui
# "taxa-acidentes" e "scorecard", que não têm motor de importação incremental
# via `/importacoes/**` (ver inventário) — mesmo assim aparecem aqui porque a
# leitura é só da tabela `IndicatorResult`, alimentada por outro caminho.
ACTIVE_INDICATOR_MODULES: tuple[str, ...] = (
    "rdo",
    "idp",
    "rnc",
    "cinco-s",
    "taxa-acidentes",
    "scorecard",
)

_HARD_CAP = 1000


async def list_indicator_results(
    session: AsyncSession, *, year: int | None = None
) -> list[IndicatorResult]:
    stmt = select(IndicatorResult).where(IndicatorResult.module.in_(ACTIVE_INDICATOR_MODULES))
    if year is not None:
        stmt = stmt.where(IndicatorResult.year == year)
    stmt = stmt.order_by(
        IndicatorResult.module.asc(), IndicatorResult.year.desc(), IndicatorResult.month.desc()
    ).limit(_HARD_CAP)
    result = await session.execute(stmt)
    return list(result.scalars().all())
