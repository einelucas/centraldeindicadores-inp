"""Testes do gerador de sugestão de justificativa da Taxa de Acidentes
(`app/modules/justifications/generators/taxa_acidentes.py`), porte de
`src/features/justifications/generators/taxa-acidentes.ts`."""

from __future__ import annotations

from app.modules.justifications.generators.taxa_acidentes import generate_accident_rate_justification
from app.modules.taxa_acidentes.types import AccidentMonthlyResult, AccidentRateResult, AccidentUnitResult


def _monthly(rate: float, caf: int = 0) -> AccidentMonthlyResult:
    return AccidentMonthlyResult(id=None, year=2027, month=3, rate=rate, caf=caf, label="Mar/2027", ok=True)


def _unit(unit: str, caf: int, saf: int, excluded: bool = False) -> AccidentUnitResult:
    return AccidentUnitResult(
        id=None, year=2027, month=3, unit=unit, unit_key=unit.lower(), saf=saf, caf=caf,
        label="Mar/2027", excluded=excluded,
    )


def _result(monthly: list[AccidentMonthlyResult], units: list[AccidentUnitResult]) -> AccidentRateResult:
    return AccidentRateResult(
        target=7.5, excluded_units=[], period=None, result=None,
        total_caf=sum(m.caf for m in monthly), total_unit_caf=sum(u.caf for u in units if not u.excluded),
        total_saf=sum(u.saf for u in units if not u.excluded), latest_rate=None, latest_year=None,
        latest_month=None, months_count=len(monthly), monthly=monthly, units=units,
    )


def test_no_data_when_no_monthly_entry() -> None:
    result = _result([], [])
    suggestion = generate_accident_rate_justification(
        result=result, previous_result=result, year=2027, month=3, source_import=None
    )
    assert suggestion.status == "NO_DATA"


def test_below_target_ranks_units_by_occurrences() -> None:
    monthly = [_monthly(9.0, caf=3)]
    units = [_unit("LEM", caf=3, saf=1), _unit("MTU", caf=0, saf=0)]
    result = _result(monthly, units)
    suggestion = generate_accident_rate_justification(
        result=result, previous_result=result, year=2027, month=3, source_import=None
    )
    assert suggestion.status == "BELOW_TARGET"  # 9.0 > meta 7.5
    assert suggestion.result == 9.0
    # "LEM" é normalizado para o nome completo da unidade no texto (format_unit_label).
    assert "LUIS EDUARDO MAGALHÃES" in suggestion.suggested_text


def test_on_target_and_caf_consistency_flagged() -> None:
    monthly = [_monthly(5.0, caf=5)]
    units = [_unit("LEM", caf=2, saf=0)]  # 5 no consolidado vs 2 por unidade -> diferença
    result = _result(monthly, units)
    suggestion = generate_accident_rate_justification(
        result=result, previous_result=result, year=2027, month=3, source_import=None
    )
    assert suggestion.status == "ON_TARGET"
    assert "diferença de 3 acidente(s) CAF" in suggestion.suggested_text


def test_previous_month_variation_and_excluded_units() -> None:
    current = _result([_monthly(6.0, caf=1)], [_unit("LEM", 1, 0), _unit("Ignorada", 5, 5, excluded=True)])
    previous = _result([_monthly(8.0, caf=2)], [_unit("LEM", 2, 0)])
    suggestion = generate_accident_rate_justification(
        result=current, previous_result=previous, year=2027, month=3, source_import=None
    )
    assert any(e.label == "Variação mensal da taxa" for e in suggestion.evidence)
    assert "1 unidade(s) ignorada(s)" in suggestion.suggested_text
