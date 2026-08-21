"""Porte literal de `tests/unit/rdo-publication.test.ts`."""

from __future__ import annotations

import pytest

from app.modules.rdo.publications import to_rdo_published_payload
from app.modules.rdo.types import RdoMonthAggregate, RdoResult, RdoUnitAggregate


def test_published_payload_basic_case() -> None:
    result = RdoResult(
        threshold=0.8,
        excluded_units=[],
        period=None,
        total_emitidos=10,
        total_aprovados=8,
        total_revisar=1,
        total_preenchendo=1,
        units=[
            RdoUnitAggregate(name="INPASA Sinop", emitidos=6, aprovados=5, aderencia=5 / 6, excluded=False),
            RdoUnitAggregate(name="Dourados", emitidos=4, aprovados=3, aderencia=0.75, excluded=False),
        ],
        unit_avg=0.0,
        months=[
            RdoMonthAggregate(year=2026, month=0, label="Jan/2026", emitidos=10, aprovados=8, aderencia=0.8)
        ],
    )

    payload = to_rdo_published_payload(result, 80)

    assert payload["resultado"] == pytest.approx(80)
    assert payload["peso"] == 0.25
    assert payload["pontos"] == 2895.5
    assert payload["emRevisaoPct"] == pytest.approx(10)
    assert payload["preenchendoPct"] == pytest.approx(10)
    assert payload["unidades"][0] == {"n": "Sinop", "v": 83}
    assert payload["mensal"] == [{"label": "Jan/2026", "v": pytest.approx(80)}]


def test_published_payload_month_without_emitidos_is_null() -> None:
    result = RdoResult(
        threshold=0.8,
        excluded_units=[],
        period=None,
        total_emitidos=250,
        total_aprovados=199,
        total_revisar=0,
        total_preenchendo=0,
        units=[],
        unit_avg=0.0,
        months=[
            RdoMonthAggregate(
                year=2026, month=5, label="Jun/2026", emitidos=250, aprovados=199, aderencia=199 / 250
            ),
            RdoMonthAggregate(year=2026, month=6, label="Jul/2026", emitidos=0, aprovados=0, aderencia=0.0),
        ],
    )

    payload = to_rdo_published_payload(result, 80)

    assert payload["resultado"] == pytest.approx(79.6)
    assert payload["mensal"][0] == {"label": "Jun/2026", "v": pytest.approx(79.6)}
    assert payload["mensal"][1] == {"label": "Jul/2026", "v": None}
