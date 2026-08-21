"""Dependência FastAPI para ler um `PeriodRange` da query string.

Porte de `parsePeriodRangeParams` (`src/lib/period.ts`). Tudo-ou-nada: só
retorna um `PeriodRange` normalizado se os 4 campos vierem presentes e
válidos (ano 2000–2200, mês 1–12); caso contrário `None` (sem restrição).

Uso em um router:

    from app.shared.period_params import period_range_query

    @router.get("/rdo")
    async def get_rdo(period: PeriodRange | None = Depends(period_range_query)):
        ...

Para o formato `.../registros` que usa os campos como corpo obrigatório (não
opcional) de um DELETE por período, use `PeriodRange` diretamente em um
schema Pydantic (CamelModel) — este helper é só para query string.
"""

from __future__ import annotations

from fastapi import Query

from app.shared.period import PeriodRange, normalize_period_range

_YEAR_MIN, _YEAR_MAX = 2000, 2200


def period_range_query(
    period_start_year: int | None = Query(default=None, alias="periodStartYear", ge=_YEAR_MIN, le=_YEAR_MAX),
    period_start_month: int | None = Query(default=None, alias="periodStartMonth", ge=1, le=12),
    period_end_year: int | None = Query(default=None, alias="periodEndYear", ge=_YEAR_MIN, le=_YEAR_MAX),
    period_end_month: int | None = Query(default=None, alias="periodEndMonth", ge=1, le=12),
) -> PeriodRange | None:
    if (
        period_start_year is None
        or period_start_month is None
        or period_end_year is None
        or period_end_month is None
    ):
        return None
    return normalize_period_range(
        PeriodRange(
            start_year=period_start_year,
            start_month=period_start_month,
            end_year=period_end_year,
            end_month=period_end_month,
        )
    )
