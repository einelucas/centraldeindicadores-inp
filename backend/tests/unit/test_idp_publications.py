"""Porte de `tests/unit/idp-publication.test.ts`."""

from __future__ import annotations

import pytest

from app.core.errors import DomainError
from app.modules.idp.publications import to_idp_published_payload
from app.modules.idp.types import (
    IdpDisciplineRow,
    IdpExecutionPhase,
    IdpMonthAggregate,
    IdpResult,
    IdpUnitRow,
)


def _unit_row(unit: str, rso_numero: int, aderencia: float, excluded: bool = False) -> IdpUnitRow:
    return IdpUnitRow(
        source_id=None, unit=unit, rso_numero=rso_numero, reference_year=2026, reference_month=6,
        reference_source="PDF_MES_REF", reference_original_text=None, reference_adjusted=False,
        period_start=None, period_end=None, emission_date=None, file_name=f"RSO {rso_numero}.pdf",
        n_fases=1, prev_acum=53.08, real_acum=53.08 * aderencia, aderencia=aderencia, excluded=excluded,
        phases=[IdpExecutionPhase(label="Fase 1", prev_acum=53.08, real_acum=53.08 * aderencia)],
    )


def test_preserva_rso_numero_referencia_e_filename_no_snapshot() -> None:
    result = IdpResult(
        threshold=0.9, excluded_disciplines=[], excluded_units=[], selected_year=2026, selected_month=6,
        history_start_year=2026, history_month_start=6, history_end_year=2026, history_month_end=7,
        active_documents=1, aderencia_geral=54.79 / 53.08, total_previsto_medio=53.08, total_real_medio=54.79,
        unit_rows=[_unit_row("Nova Mutum", 34, 54.79 / 53.08)],
        discipline_rows=[
            IdpDisciplineRow(disciplina="01 - Civil", prev_avg=100, real_avg=99.5, aderencia=0.995)
        ],
        monthly=[
            IdpMonthAggregate(
                year=2026, month=6, label="Junho/2026", aderencia=54.79 / 53.08,
                active_documents=1, total_previsto_medio=53.08, total_real_medio=54.79,
            ),
            IdpMonthAggregate(
                year=2026, month=7, label="Julho/2026", aderencia=None,
                active_documents=0, total_previsto_medio=0, total_real_medio=0,
            ),
        ],
    )

    payload = to_idp_published_payload(result, 90)

    assert payload["unidades"][0]["n"] == "Nova Mutum"
    assert payload["unidades"][0]["rsoNumero"] == 34
    assert payload["unidades"][0]["referenceYear"] == 2026
    assert payload["unidades"][0]["referenceMonth"] == 6
    assert payload["unidades"][0]["fileName"] == "RSO 34.pdf"
    assert payload["mensal"][1]["v"] is None  # julho sem RSO no historyRange
    assert payload["pontos"] == 4053.7
    assert payload["peso"] == 0.35


def test_nao_permite_publicacao_sem_execucao_prevista_valida() -> None:
    result = IdpResult(
        threshold=0.9, excluded_disciplines=[], excluded_units=[], selected_year=2026, selected_month=6,
        history_start_year=2026, history_month_start=6, history_end_year=2026, history_month_end=6,
        active_documents=0, aderencia_geral=None, total_previsto_medio=0, total_real_medio=0,
        unit_rows=[], discipline_rows=[], monthly=[],
    )
    with pytest.raises(DomainError, match=r"(?i)execu"):
        to_idp_published_payload(result, 90)


def test_todas_unidades_ativas_excluidas_nao_derruba_com_500() -> None:
    """Correção aplicada (decisions.md §4.2.5): `activeDocuments > 0` mas
    `totalPrevistoMedio == 0` (todas as unidades ativas excluídas) levanta
    `DomainError` (-> 422) em vez de um erro genérico não capturado (-> 500)."""
    result = IdpResult(
        threshold=0.9, excluded_disciplines=[], excluded_units=["Nova Mutum"], selected_year=2026,
        selected_month=6, history_start_year=2026, history_month_start=6, history_end_year=2026,
        history_month_end=6, active_documents=1, aderencia_geral=None, total_previsto_medio=0,
        total_real_medio=0, unit_rows=[_unit_row("Nova Mutum", 34, 54.79 / 53.08, excluded=True)],
        discipline_rows=[], monthly=[],
    )
    with pytest.raises(DomainError):
        to_idp_published_payload(result, 90)
