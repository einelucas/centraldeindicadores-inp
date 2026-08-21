"""Schemas Pydantic da rota de indicadores consolidados. Porte de
`src/app/api/indicadores/route.ts`."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.shared.schema import CamelModel


class IndicatorResultOut(CamelModel):
    id: str
    module: str
    indicator: str
    unit: str
    year: int
    month: int
    value: float | None
    target: float | None
    adherence: float | None
    status: str | None
    details: dict[str, Any] | None
    updated_at: datetime


class IndicatorResultListOut(CamelModel):
    items: list[IndicatorResultOut]
