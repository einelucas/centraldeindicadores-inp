"""Testes do gerador de sugestão de justificativa do 5S
(`app/modules/justifications/generators/cinco_s.py`), porte de
`src/features/justifications/generators/cinco-s.ts`."""

from __future__ import annotations

from app.modules.cinco_s.types import FiveSArea, FiveSResult, FiveSUnitMonth
from app.modules.justifications.generators.cinco_s import generate_five_s_justification


def _unit_month(unit: str, areas: list[FiveSArea], excluded: bool = False) -> FiveSUnitMonth:
    aderencia = sum(min(a.nota / a.meta, 1.0) for a in areas) / len(areas)
    return FiveSUnitMonth(unit=unit, year=2027, month=3, aderencia=aderencia, excluded=excluded, areas=areas)


def _result(unit_months: list[FiveSUnitMonth], threshold: float = 0.9) -> FiveSResult:
    return FiveSResult(
        threshold=threshold, excluded_units=[], period=None, period_label="", latest_year=2027,
        latest_month=3, geral=None, passa_meta=False, unit_months=unit_months, months=[],
        units_count=len(unit_months), months_count=1,
    )


def test_no_data_when_no_units_in_month() -> None:
    result = _result([])
    suggestion = generate_five_s_justification(
        result=result, previous_result=result, year=2027, month=3, source_import=None
    )
    assert suggestion.status == "NO_DATA"


def test_below_target_lists_area_deviations() -> None:
    unit = _unit_month("LEM", [FiveSArea(divisao="Área 1", area="Almoxarifado", meta=1.0, nota=0.5)])
    result = _result([unit])
    suggestion = generate_five_s_justification(
        result=result, previous_result=result, year=2027, month=3, source_import=None
    )
    assert suggestion.status == "BELOW_TARGET"
    assert "Almoxarifado" in suggestion.suggested_text
    assert any(e.label == "Áreas abaixo da meta" for e in suggestion.evidence)


def test_on_target_when_areas_meet_meta() -> None:
    unit = _unit_month("LEM", [FiveSArea(divisao="Área 1", area="Almoxarifado", meta=1.0, nota=0.95)])
    result = _result([unit])
    suggestion = generate_five_s_justification(
        result=result, previous_result=result, year=2027, month=3, source_import=None
    )
    assert suggestion.status == "ON_TARGET"
    assert "Nenhuma unidade incluída ficou abaixo da meta" in suggestion.suggested_text


def test_previous_month_variation_and_excluded_unit() -> None:
    current = _result([
        _unit_month("LEM", [FiveSArea(divisao=None, area="A", meta=1.0, nota=0.6)]),
        _unit_month("Ignorada", [FiveSArea(divisao=None, area="B", meta=1.0, nota=0.1)], excluded=True),
    ])
    previous = _result([_unit_month("LEM", [FiveSArea(divisao=None, area="A", meta=1.0, nota=0.9)])])
    suggestion = generate_five_s_justification(
        result=current, previous_result=previous, year=2027, month=3, source_import=None
    )
    assert any(e.label == "Variação mensal" for e in suggestion.evidence)
    assert "1 unidade(s) ignorada(s)" in suggestion.suggested_text
