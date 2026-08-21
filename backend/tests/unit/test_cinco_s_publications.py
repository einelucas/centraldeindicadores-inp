"""Porte de `tests/unit/cinco-s-publication.test.ts`."""

from __future__ import annotations

import pytest

from app.modules.cinco_s.publications import (
    FiveSPublicationError,
    five_s_published_payload_to_json,
    to_five_s_published_payload,
)
from app.modules.cinco_s.types import FiveSMonthResult, FiveSResult, FiveSUnitMonth


def test_publish_uses_latest_month_units() -> None:
    result = FiveSResult(
        threshold=0.9,
        excluded_units=[],
        period=None,
        period_label="Mar/2027",
        latest_year=2027,
        latest_month=3,
        geral=0.75,
        passa_meta=False,
        unit_months=[
            FiveSUnitMonth(unit="LEM", year=2027, month=3, aderencia=1.0, excluded=False, areas=[]),
            FiveSUnitMonth(unit="MTU", year=2027, month=3, aderencia=0.5, excluded=False, areas=[]),
            FiveSUnitMonth(unit="RVD", year=2027, month=2, aderencia=0.2, excluded=False, areas=[]),
        ],
        months=[
            FiveSMonthResult(year=2027, month=2, label="Fev/2027", geral=0.2, units_count=1),
            FiveSMonthResult(year=2027, month=3, label="Mar/2027", geral=0.75, units_count=2),
        ],
        units_count=3,
        months_count=2,
    )

    payload = to_five_s_published_payload(result)

    assert payload.resultado == 75
    assert payload.meta == 90
    assert len(payload.unidades) == 2
    assert payload.unidades[0].n == "LEM"
    assert len(payload.mensal) == 2

    json_payload = five_s_published_payload_to_json(payload)
    assert json_payload["referenceYear"] == 2027
    assert json_payload["referenceMonth"] == 3


def test_publish_without_eligible_units_raises() -> None:
    result = FiveSResult(
        threshold=0.9, excluded_units=[], period=None, period_label="—", latest_year=None,
        latest_month=None, geral=None, passa_meta=False, unit_months=[], months=[],
        units_count=0, months_count=0,
    )
    with pytest.raises(FiveSPublicationError):
        to_five_s_published_payload(result)
