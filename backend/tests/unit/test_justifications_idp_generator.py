"""Testes do gerador de sugestão de justificativa do IDP
(`app/modules/justifications/generators/idp.py`), porte de
`src/features/justifications/generators/idp.ts`."""

from __future__ import annotations

from app.modules.idp.types import (
    IdpDisciplineRow,
    IdpExecutionPhase,
    IdpMonthAggregate,
    IdpResult,
    IdpUnitRow,
)
from app.modules.justifications.generators.idp import generate_idp_justification


def _unit(
    unit: str, aderencia: float, prev: float = 50.0, real: float | None = None, excluded: bool = False
) -> IdpUnitRow:
    actual_real = real if real is not None else prev * aderencia
    return IdpUnitRow(
        source_id=None, unit=unit, rso_numero=1, reference_year=2027, reference_month=3,
        reference_source="PDF_MES_REF", reference_original_text=None, reference_adjusted=False,
        period_start=None, period_end=None, emission_date=None, file_name="RSO 1.pdf",
        n_fases=1, prev_acum=prev, real_acum=actual_real, aderencia=aderencia, excluded=excluded,
        phases=[IdpExecutionPhase(label="Fase 1", prev_acum=prev, real_acum=actual_real)],
    )


def _empty_result(*, unit_rows: list[IdpUnitRow] | None = None, threshold: float = 0.9) -> IdpResult:
    unit_rows = unit_rows or []
    included = [u for u in unit_rows if not u.excluded]
    aderencia_values = [u.aderencia for u in included if u.aderencia is not None]
    aderencia_geral = sum(aderencia_values) / len(aderencia_values) if aderencia_values else None
    return IdpResult(
        threshold=threshold, excluded_disciplines=[], excluded_units=[], selected_year=2027,
        selected_month=3, history_start_year=2027, history_month_start=3, history_end_year=2027,
        history_month_end=3, active_documents=len(unit_rows), aderencia_geral=aderencia_geral,
        total_previsto_medio=sum(u.prev_acum for u in included),
        total_real_medio=sum(u.real_acum for u in included), unit_rows=unit_rows,
        discipline_rows=[
            IdpDisciplineRow(disciplina="01 - Civil", prev_avg=50.0, real_avg=25.0, aderencia=0.5)
        ],
        monthly=[
            IdpMonthAggregate(year=2027, month=3, label="Março/2027", aderencia=aderencia_geral,
                               active_documents=len(unit_rows), total_previsto_medio=0, total_real_medio=0)
        ],
    )


def test_no_data_when_no_included_units() -> None:
    result = _empty_result(unit_rows=[])
    suggestion = generate_idp_justification(result=result, previous_result=result, source_import=None)
    assert suggestion.status == "NO_DATA"
    assert suggestion.evidence == []


def test_below_target_ranks_units_and_phase_deviations() -> None:
    result = _empty_result(unit_rows=[_unit("Nova Mutum", 0.5), _unit("Rio Verde", 0.95)])
    suggestion = generate_idp_justification(result=result, previous_result=result, source_import=None)
    assert suggestion.status == "BELOW_TARGET"  # média (0.5+0.95)/2 = 0.725 < 0.9
    assert any(e.label == "Maior desvio de fase" for e in suggestion.evidence)
    assert "Nova Mutum" in suggestion.suggested_text


def test_on_target_when_all_units_meet_threshold() -> None:
    result = _empty_result(unit_rows=[_unit("Nova Mutum", 0.95), _unit("Rio Verde", 0.92)])
    suggestion = generate_idp_justification(result=result, previous_result=result, source_import=None)
    assert suggestion.status == "ON_TARGET"
    assert "Nenhuma unidade incluída ficou abaixo da meta" in suggestion.suggested_text


def test_excluded_unit_stays_out_of_evidence_but_counts_in_excluded_line() -> None:
    result = _empty_result(unit_rows=[_unit("Nova Mutum", 0.95), _unit("Ignorada", 0.1, excluded=True)])
    suggestion = generate_idp_justification(result=result, previous_result=result, source_import=None)
    assert suggestion.status == "ON_TARGET"  # só Nova Mutum conta
    assert "1 unidade(s) marcada(s) como ignorada(s)" in suggestion.suggested_text


def test_previous_result_adds_variation_evidence() -> None:
    current = _empty_result(unit_rows=[_unit("Nova Mutum", 0.95)])
    previous = _empty_result(unit_rows=[_unit("Nova Mutum", 0.80)])
    suggestion = generate_idp_justification(result=current, previous_result=previous, source_import=None)
    assert any(e.label == "Variação mensal" for e in suggestion.evidence)
