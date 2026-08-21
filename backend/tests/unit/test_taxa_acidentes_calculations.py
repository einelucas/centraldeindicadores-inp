"""Porte de `tests/unit/taxa-acidentes-calculations.test.ts`."""

from __future__ import annotations

from app.modules.taxa_acidentes.calculations import compute_accident_rate_result, month_label
from app.modules.taxa_acidentes.types import AccidentMonthlyInput, AccidentUnitInput


def test_month_label_full_name() -> None:
    assert month_label(2026, 2) == "Fevereiro/2026"


def test_result_is_simple_average_of_months() -> None:
    monthly = [
        AccidentMonthlyInput(year=2027, month=1, rate=5.0, caf=1),
        AccidentMonthlyInput(year=2027, month=2, rate=10.0, caf=2),
    ]
    result = compute_accident_rate_result(monthly, [], target=7.5, excluded_units=[])
    assert result.result == 7.5
    assert result.total_caf == 3


def test_latest_rate_is_most_recent_month() -> None:
    monthly = [
        AccidentMonthlyInput(year=2027, month=1, rate=5.0, caf=1),
        AccidentMonthlyInput(year=2027, month=3, rate=9.0, caf=1),
        AccidentMonthlyInput(year=2027, month=2, rate=1.0, caf=1),
    ]
    result = compute_accident_rate_result(monthly, [], target=7.5, excluded_units=[])
    assert result.latest_year == 2027
    assert result.latest_month == 3
    assert result.latest_rate == 9.0


def test_duplicate_year_month_last_occurrence_wins() -> None:
    monthly = [
        AccidentMonthlyInput(year=2027, month=1, rate=5.0, caf=1),
        AccidentMonthlyInput(year=2027, month=1, rate=8.0, caf=3),
    ]
    result = compute_accident_rate_result(monthly, [], target=7.5, excluded_units=[])
    assert result.result == 8.0
    assert result.total_caf == 3
    assert result.months_count == 1


def test_unit_caf_and_saf_kept_separate() -> None:
    units = [
        AccidentUnitInput(year=2027, month=1, unit="LEM", unit_key="lem", saf=2, caf=1),
        AccidentUnitInput(year=2027, month=1, unit="MTU", unit_key="mtu", saf=0, caf=3),
    ]
    result = compute_accident_rate_result([], units, target=7.5, excluded_units=[])
    assert result.total_unit_caf == 4
    assert result.total_saf == 2
