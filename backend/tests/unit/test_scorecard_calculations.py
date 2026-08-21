"""Porte de `tests/unit/scorecard-calculations.test.ts` e `tests/scorecard-points.test.ts`
(este último nunca rodava via `pnpm test` no TS — ver
docs/backend-migration-decisions.md §1.2 — mas o conteúdo permanece válido)."""

from __future__ import annotations

import pytest

from app.modules.scorecard.calculations import (
    compute_scorecard,
    indicator_monthly_points,
    merge_live_with_saved_fallback,
    score_indicator,
)
from app.modules.scorecard.types import SC_INDICATORS, SCORECARD_MAX_POINTS, SCORECARD_MONTHLY_POOL


def test_five_indicators_weights_sum_to_100() -> None:
    assert len(SC_INDICATORS) == 5
    assert sum(i.peso for i in SC_INDICATORS) == 100


def test_monthly_pool_times_six_equals_max_points() -> None:
    assert pytest.approx(SCORECARD_MAX_POINTS, abs=1e-9) == SCORECARD_MONTHLY_POOL * 6


def test_monthly_pool_distributed_by_weight() -> None:
    total = sum(indicator_monthly_points(i) for i in SC_INDICATORS)
    assert total == pytest.approx(SCORECARD_MONTHLY_POOL, abs=1e-9)


def test_all_indicators_meeting_target_gets_full_points() -> None:
    values = {i.key: i.meta for i in SC_INDICATORS}
    result = compute_scorecard(values)
    assert result.total_pontos == pytest.approx(SCORECARD_MONTHLY_POOL, abs=1e-9)
    assert result.atendimento_mes == pytest.approx(100, abs=1e-9)


def test_binary_scoring_no_partial_credit() -> None:
    rdo = SC_INDICATORS[0]
    just_below = score_indicator(rdo, rdo.meta - 0.01)
    assert just_below.passed is False
    assert just_below.pontos == 0.0


def test_exact_meta_counts_as_met_higher_direction() -> None:
    rdo = next(i for i in SC_INDICATORS if i.direction == "higher")
    scored = score_indicator(rdo, rdo.meta)
    assert scored.passed is True


def test_exact_meta_counts_as_met_lower_direction() -> None:
    rnc = next(i for i in SC_INDICATORS if i.direction == "lower")
    scored = score_indicator(rnc, rnc.meta)
    assert scored.passed is True


def test_missing_value_scores_zero_not_treated_as_meeting_target() -> None:
    rdo = SC_INDICATORS[0]
    scored = score_indicator(rdo, None)
    assert scored.has_value is False
    assert scored.passed is False
    assert scored.pontos == 0.0


def test_december_crosses_year_handled_by_shared_period_module() -> None:
    from app.shared.period import get_operational_period

    result = get_operational_period(2026, 12)
    assert result.period_year == 2027
    assert result.semester.value == "S1"


def test_merge_live_with_saved_fallback_live_wins() -> None:
    live = {"rdo": 85.0, "rnc": None}
    saved = {"rdo": 50.0, "rnc": 12.0}
    merged = merge_live_with_saved_fallback(live, saved)
    assert merged["rdo"] == 85.0  # ao vivo vence
    assert merged["rnc"] == 12.0  # sem ao vivo -> respaldo do snapshot


def test_merge_live_with_saved_fallback_no_live_no_saved_is_none() -> None:
    merged = merge_live_with_saved_fallback({}, {})
    assert all(v is None for v in merged.values())
