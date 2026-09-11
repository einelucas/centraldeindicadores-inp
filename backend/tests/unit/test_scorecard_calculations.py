"""Testes do motor do Scorecard sob o alinhamento 2026-alinhamento-v2 (RDO
35% / Cronograma 40% / RNC 15% / Horas Extras 10% reservado, em
desenvolvimento). Porte/extensão de `tests/unit/scorecard-calculations.test.ts`
e `tests/scorecard-points.test.ts`."""

from __future__ import annotations

import pytest

from app.modules.scorecard.calculations import (
    compute_general_panel,
    compute_scorecard,
    indicator_monthly_points,
    merge_live_with_saved_fallback,
    score_indicator,
)
from app.modules.scorecard.types import (
    SC_ACTIVE_INDICATORS,
    SC_INDICATORS,
    SCORECARD_ACTIVE_COVERAGE_PCT,
    SCORECARD_ACTIVE_WEIGHT_TOTAL,
    SCORECARD_MAX_POINTS,
    SCORECARD_MONTHLY_POOL,
    SCORECARD_OFFICIAL_WEIGHT_TOTAL,
    SCORECARD_RESERVED_WEIGHT_TOTAL,
    ActiveScorecardIndicator,
    DevelopmentScorecardIndicator,
)


def test_four_official_indicators() -> None:
    assert len(SC_INDICATORS) == 4
    assert {i.key for i in SC_INDICATORS} == {"rdo", "cronograma", "rnc", "horas_extras"}


def test_official_weights_sum_to_100() -> None:
    assert pytest.approx(100, abs=1e-9) == SCORECARD_OFFICIAL_WEIGHT_TOTAL
    assert sum(i.peso for i in SC_INDICATORS) == pytest.approx(100, abs=1e-9)


def test_active_weights_sum_to_90() -> None:
    assert pytest.approx(90, abs=1e-9) == SCORECARD_ACTIVE_WEIGHT_TOTAL
    assert sum(i.peso for i in SC_ACTIVE_INDICATORS) == pytest.approx(90, abs=1e-9)


def test_reserved_weight_is_10() -> None:
    assert pytest.approx(10, abs=1e-9) == SCORECARD_RESERVED_WEIGHT_TOTAL


def test_active_coverage_is_90_pct() -> None:
    assert pytest.approx(90.0, abs=1e-9) == SCORECARD_ACTIVE_COVERAGE_PCT


def test_individual_weights() -> None:
    by_key = {i.key: i.peso for i in SC_INDICATORS}
    assert by_key["rdo"] == 35
    assert by_key["cronograma"] == 40
    assert by_key["rnc"] == 15
    assert by_key["horas_extras"] == 10


def test_horas_extras_is_development_not_scored() -> None:
    horas_extras = next(i for i in SC_INDICATORS if i.key == "horas_extras")
    assert isinstance(horas_extras, DevelopmentScorecardIndicator)
    assert horas_extras.scoring_enabled is False
    assert horas_extras.status == "development"
    assert horas_extras.meta_reference == 1
    assert horas_extras.area == "RH"


def test_monthly_pool_times_six_equals_max_points() -> None:
    assert pytest.approx(SCORECARD_MAX_POINTS, abs=1e-9) == SCORECARD_MONTHLY_POOL * 6


def test_monthly_pool_distributed_by_official_weight() -> None:
    total = sum(indicator_monthly_points(i) for i in SC_INDICATORS)
    assert total == pytest.approx(SCORECARD_MONTHLY_POOL, abs=1e-9)


def test_cycle_and_monthly_points_match_spec_values() -> None:
    by_key = {i.key: i for i in SC_INDICATORS}
    expectations_monthly = {
        "rdo": 675.616667,
        "cronograma": 772.133333,
        "rnc": 289.55,
        "horas_extras": 193.033333,
    }
    for key, expected_monthly in expectations_monthly.items():
        monthly = indicator_monthly_points(by_key[key])
        assert monthly == pytest.approx(expected_monthly, abs=1e-5)
        assert monthly * 6 == pytest.approx(expected_monthly * 6, abs=1e-4)

    assert indicator_monthly_points(by_key["rdo"]) * 6 == pytest.approx(4053.70, abs=1e-2)
    assert indicator_monthly_points(by_key["cronograma"]) * 6 == pytest.approx(4632.80, abs=1e-2)
    assert indicator_monthly_points(by_key["rnc"]) * 6 == pytest.approx(1737.30, abs=1e-2)
    assert indicator_monthly_points(by_key["horas_extras"]) * 6 == pytest.approx(1158.20, abs=1e-2)


def test_score_indicator_only_accepts_active_indicators() -> None:
    """`score_indicator` exige `ActiveScorecardIndicator` — este teste prova
    que os três indicadores ativos passam por ele; `horas_extras` (dev)
    nunca é passado (o compilador já bloqueia isso, ver types.py)."""
    for indicator in SC_ACTIVE_INDICATORS:
        scored = score_indicator(indicator, indicator.meta)
        assert scored.passed is True


def test_three_actives_at_target_yields_1737_30_points_and_100pct_active_attendance() -> None:
    values = {i.key: i.meta for i in SC_ACTIVE_INDICATORS}
    result = compute_scorecard(values)
    assert result.total_pontos == pytest.approx(1737.30, abs=1e-2)
    assert result.atendimento_mes == pytest.approx(100.0, abs=1e-9)
    assert result.pontos_possiveis_mes == pytest.approx(1737.30, abs=1e-2)
    assert result.pontos_oficiais_mes == pytest.approx(1930.333333, abs=1e-5)
    assert result.pontos_reservados_mes == pytest.approx(193.033333, abs=1e-5)
    assert result.cobertura_ativa_pct == pytest.approx(90.0, abs=1e-9)


def test_horas_extras_row_never_scores_even_if_value_supplied() -> None:
    """Mesmo que `values` contenha um número indevido para `horas_extras`,
    a linha nunca pontua — `compute_scorecard` nunca avalia indicadores em
    desenvolvimento."""
    values = {i.key: i.meta for i in SC_ACTIVE_INDICATORS}
    values["horas_extras"] = 999.0  # nunca deveria influenciar nada
    result = compute_scorecard(values)

    row = next(r for r in result.rows if r.key == "horas_extras")
    assert row.scoring_enabled is False
    assert row.status == "development"
    assert row.pontos == 0.0
    assert row.has_value is False
    assert row.passed is False
    assert row.value is None
    # Não contamina o total nem o atendimento dos ativos.
    assert result.total_pontos == pytest.approx(1737.30, abs=1e-2)
    assert result.atendimento_mes == pytest.approx(100.0, abs=1e-9)


def test_horas_extras_absence_does_not_reduce_active_attendance() -> None:
    """Comparar o resultado com e sem `horas_extras` em `values` — o
    atendimento dos ativos é idêntico, porque o denominador já é só o pool
    contabilizável."""
    values_without = {i.key: i.meta for i in SC_ACTIVE_INDICATORS}
    values_with = {**values_without, "horas_extras": 1.0}

    result_without = compute_scorecard(values_without)
    result_with = compute_scorecard(values_with)

    assert result_without.atendimento_mes == pytest.approx(result_with.atendimento_mes, abs=1e-9)
    assert result_without.total_pontos == pytest.approx(result_with.total_pontos, abs=1e-9)


def test_binary_scoring_no_partial_credit() -> None:
    rdo = next(i for i in SC_ACTIVE_INDICATORS if i.key == "rdo")
    just_below = score_indicator(rdo, rdo.meta - 0.01)
    assert just_below.passed is False
    assert just_below.pontos == 0.0


def test_exact_meta_counts_as_met_higher_direction() -> None:
    rdo = next(i for i in SC_ACTIVE_INDICATORS if i.direction == "higher")
    scored = score_indicator(rdo, rdo.meta)
    assert scored.passed is True


def test_exact_meta_counts_as_met_lower_direction() -> None:
    rnc = next(i for i in SC_ACTIVE_INDICATORS if i.direction == "lower")
    scored = score_indicator(rnc, rnc.meta)
    assert scored.passed is True


def test_missing_value_scores_zero_not_treated_as_meeting_target() -> None:
    rdo = next(i for i in SC_ACTIVE_INDICATORS if i.key == "rdo")
    scored = score_indicator(rdo, None)
    assert scored.has_value is False
    assert scored.passed is False
    assert scored.pontos == 0.0


def test_5s_and_taxa_acidentes_are_not_scorecard_indicators() -> None:
    keys = {i.key for i in SC_INDICATORS}
    assert "5s" not in keys
    assert "taxa_acidentes" not in keys


def test_5s_key_in_values_is_silently_ignored() -> None:
    """Um `values` com uma chave de indicador antigo (não mais em
    `SC_INDICATORS`) nunca aparece no resultado — sem erro de parsing."""
    values = {i.key: i.meta for i in SC_ACTIVE_INDICATORS}
    values["5s"] = 95.0
    values["taxa_acidentes"] = 3.0
    result = compute_scorecard(values)
    assert {row.key for row in result.rows} == {"rdo", "cronograma", "rnc", "horas_extras"}


def test_no_rounding_drift_across_six_months() -> None:
    values = {i.key: i.meta for i in SC_ACTIVE_INDICATORS}
    total = sum(compute_scorecard(values).total_pontos for _ in range(6))
    assert total == pytest.approx(1737.30 * 6, abs=1e-2)
    assert total == pytest.approx(10_423.80, abs=1e-2)


def test_activating_horas_extras_switches_active_coverage_to_100_without_redistribution() -> None:
    """Simula "ativar" Horas Extras trocando o item por um indicador ATIVO
    equivalente — o motor de cálculo não precisa de nenhuma mudança; o peso
    contabilizável passa a 100% automaticamente, sem redistribuir os pesos
    dos outros três indicadores."""
    from app.modules.scorecard.types import IndicatorSource

    activated_horas_extras = ActiveScorecardIndicator(
        key="horas_extras", label="Horas Extras Pagas", area="RH", peso=10,
        meta=1, direction="lower", unit="",
        source=IndicatorSource(module="horas-extras", indicator="valor"),
    )
    indicators = (*SC_ACTIVE_INDICATORS, activated_horas_extras)

    assert sum(i.peso for i in indicators) == pytest.approx(100, abs=1e-9)
    for i in indicators:
        if i.key in {"rdo", "cronograma", "rnc"}:
            original = next(x for x in SC_INDICATORS if x.key == i.key)
            assert i.peso == original.peso  # pesos originais preservados, sem redistribuição

    values = {i.key: i.meta for i in indicators}
    result = compute_scorecard(values, indicators=indicators)
    assert result.pontos_possiveis_mes == pytest.approx(SCORECARD_MONTHLY_POOL, abs=1e-6)
    assert result.atendimento_mes == pytest.approx(100.0, abs=1e-9)


def test_merge_live_with_saved_fallback_live_wins() -> None:
    live = {"rdo": 85.0, "rnc": None}
    saved = {"rdo": 50.0, "rnc": 12.0}
    merged = merge_live_with_saved_fallback(live, saved)
    assert merged["rdo"] == 85.0  # ao vivo vence
    assert merged["rnc"] == 12.0  # sem ao vivo -> respaldo do snapshot


def test_merge_live_with_saved_fallback_no_live_no_saved_is_none() -> None:
    merged = merge_live_with_saved_fallback({}, {})
    assert all(v is None for v in merged.values())


def test_december_crosses_year_handled_by_shared_period_module() -> None:
    from app.shared.period import get_operational_period

    result = get_operational_period(2026, 12)
    assert result.period_year == 2027
    assert result.semester.value == "S1"


def test_general_panel_never_contains_5s_or_taxa_acidentes() -> None:
    panel = compute_general_panel(publications=[], period=None)
    keys = {i.key for i in panel.indicators}
    assert keys == {"rdo", "cronograma", "rnc", "horas_extras"}


def test_general_panel_horas_extras_row_is_reserved_not_scored() -> None:
    panel = compute_general_panel(publications=[], period=None)
    horas_extras = next(i for i in panel.indicators if i.key == "horas_extras")
    assert horas_extras.scoring_enabled is False
    assert horas_extras.status == "development"
    assert horas_extras.passed is None
    assert horas_extras.partial_pass is None
    assert horas_extras.has_data is False
