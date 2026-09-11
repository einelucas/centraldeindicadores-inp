"""Porte de `tests/unit/idp-calculations.test.ts`.

Nota: alguns testes originais chamam `computeIdpResult` com um override
explícito `{selectedYear, selectedMonth, historyMonthStart, historyMonthEnd}`
— uma flexibilidade de assinatura que nenhuma rota FastAPI usa (todas
derivam a competência selecionada a partir de um `PeriodRange`, ver
`_resolve_selected_and_history`). Onde a resolução por período não
reproduz exatamente o cenário do teste original (test 4 — competência
selecionada SEM dado, histórico cobrindo um mês anterior COM dado), o
comportamento é validado diretamente nas funções primitivas
(`records_in_competence`, `select_latest_rso_by_unit`), que é o que a regra
de negócio realmente testa (RSO não vaza de um mês para outro)."""

from __future__ import annotations

import pytest

from app.modules.idp.calculations import (
    calculate_idp_adherence,
    compute_idp_result,
    is_idp_discipline_excluded,
    normalize_idp_discipline_name,
    records_in_competence,
    select_latest_rso_by_unit,
)
from app.modules.idp.types import IdpAreaEntry, IdpExecutionPhase, IdpNormalizedRecord
from app.shared.period import PeriodRange


def _record(
    unit: str = "Nova Mutum",
    rso_numero: int = 34,
    year: int = 2026,
    month: int = 6,
    civil_prev: float = 100,
    civil_real: float = 99.5,
    fase_prev: float = 53.08,
    fase_real: float = 54.79,
    fases: list[IdpExecutionPhase] | None = None,
) -> IdpNormalizedRecord:
    return IdpNormalizedRecord(
        unit=unit, detected_unit=unit, unit_adjusted=False, rso_numero=rso_numero,
        detected_rso_numero=rso_numero, rso_adjusted=False, reference_year=year, reference_month=month,
        detected_reference_year=year, detected_reference_month=month, reference_source="PDF_MES_REF",
        reference_original_text=None, reference_adjusted=False, period_start=None, period_end=None,
        emission_date=None, file_name=f"RSO {rso_numero}.pdf", areas=["Pipe Rack"],
        disc_data={
            "01 - Civil": [IdpAreaEntry(area="Pipe Rack", prev_acum=civil_prev, real_acum=civil_real)]
        },
        execucao_fases=fases
        or [IdpExecutionPhase(label="Fase 1", prev_acum=fase_prev, real_acum=fase_real)],
        raw={},
    )


def test_aderencia_realizado_sobre_previsto() -> None:
    result = calculate_idp_adherence(54.79, 53.08)
    assert result == pytest.approx(54.79 / 53.08)


def test_baseline_zero_retorna_zero() -> None:
    """Paridade com o TS original: previsto==0 (ou não finito) retorna 0.0,
    não None — ver docs/backend-migration-decisions.md §4.2.1."""
    assert calculate_idp_adherence(10.0, 0.0) == 0.0
    assert calculate_idp_adherence(0.0, 0.0) == 0.0


def test_normaliza_caixa_acentos_espacos_hifens_e_sublinhados() -> None:
    """Porte de `tests/unit/idp-configuration.test.ts` — casos de
    normalização de nome de disciplina não cobertos por outro teste."""
    assert normalize_idp_discipline_name(" 09 _ PROJÉTOS ") == "09 projetos"
    assert normalize_idp_discipline_name("10---Fornecimentos") == "10 fornecimentos"


def test_is_idp_discipline_excluded_identifica_variacoes() -> None:
    excluded = ["09 _ Projetos", "10 _ Fornecimentos"]
    assert is_idp_discipline_excluded("09-Projetos", excluded) is True
    assert is_idp_discipline_excluded("01 - Civil", excluded) is False


def test_seleciona_o_maior_rso_da_mesma_unidade_e_competencia() -> None:
    entries = [_record(rso_numero=32), _record(rso_numero=34), _record(rso_numero=33)]
    winners = select_latest_rso_by_unit(entries)
    assert len(winners) == 1
    assert winners[0].rso_numero == 34


def test_normaliza_caixa_e_acentuacao_da_unidade_ao_escolher_versao_ativa() -> None:
    entries = [_record(unit="RIO VERDE", rso_numero=37), _record(unit="Rio Verde", rso_numero=38)]
    winners = select_latest_rso_by_unit(entries)
    assert len(winners) == 1
    assert winners[0].rso_numero == 38


def test_nao_carrega_rso_de_junho_para_julho() -> None:
    rows = [_record(month=6, rso_numero=34)]
    assert records_in_competence(rows, 2026, 7) == []
    assert records_in_competence(rows, 2026, 6) == rows


def test_mantem_versoes_semanais_no_historico_mas_calcula_apenas_a_maior_versao() -> None:
    entries = [
        _record(unit="Nova Mutum", rso_numero=32, fase_prev=50, fase_real=45),
        _record(unit="Nova Mutum", rso_numero=34, fase_prev=53.08, fase_real=54.79),
        _record(
            unit="Rio Verde", rso_numero=38,
            fases=[
                IdpExecutionPhase(label="Fase 1", prev_acum=51.23, real_acum=49.5),
                IdpExecutionPhase(label="Fase 2", prev_acum=25.55, real_acum=26.93),
            ],
        ),
    ]
    period = PeriodRange(start_year=2026, start_month=6, end_year=2026, end_month=6)
    result = compute_idp_result(entries, 0.9, [], [], period)

    assert result.active_documents == 2  # 2 unidades, não 3 registros
    # `IdpUnitRow.unit` é sempre o nome completo canônico (nunca a sigla nem
    # o texto bruto do PDF) — ver app/shared/units.py::format_unit_label.
    nova_mutum = next(u for u in result.unit_rows if u.unit == "NOVA MUTUM")
    assert nova_mutum.rso_numero == 34  # não 32
    rio_verde = next(u for u in result.unit_rows if u.unit == "RIO VERDE")
    assert rio_verde.n_fases == 2


def test_disciplina_excluida_nao_entra_em_discipline_rows() -> None:
    entries = [_record()]
    result = compute_idp_result(
        entries, 0.9, ["01 - Civil"], [],
        PeriodRange(start_year=2026, start_month=6, end_year=2026, end_month=6),
    )
    assert all(row.disciplina != "01 - Civil" for row in result.discipline_rows)


def test_unidade_excluida_fica_fora_da_aderencia_geral_mas_aparece_em_unit_rows() -> None:
    entries = [_record(unit="Ignorada", fase_prev=50, fase_real=10)]
    result = compute_idp_result(
        entries, 0.9, [], ["Ignorada"],
        PeriodRange(start_year=2026, start_month=6, end_year=2026, end_month=6),
    )
    assert result.active_documents == 1
    assert result.aderencia_geral is None  # nenhuma unidade incluída
    unit_row = result.unit_rows[0]
    assert unit_row.excluded is True
    assert unit_row.aderencia == pytest.approx(0.2)  # ainda calculado, só não entra no geral


def test_unit_row_exposes_discipline_area_breakdown_for_unit_detail() -> None:
    """`unit_rows[].disciplines` alimenta o "Detalhamento por unidade" do
    painel administrativo (unidade -> disciplina -> área)."""
    entries = [_record(unit="Nova Mutum", civil_prev=100, civil_real=99.5)]
    result = compute_idp_result(
        entries, 0.9, [], [],
        PeriodRange(start_year=2026, start_month=6, end_year=2026, end_month=6),
    )
    unit_row = result.unit_rows[0]
    assert len(unit_row.disciplines) == 1
    civil = unit_row.disciplines[0]
    assert civil.disciplina == "01 - Civil"
    assert civil.areas == [IdpAreaEntry(area="Pipe Rack", prev_acum=100, real_acum=99.5)]
    assert civil.aderencia == pytest.approx(0.995)
    # Disciplinas sem nenhuma área reconhecida no RSO não aparecem no detalhamento.
    assert all(d.disciplina != "02 - Mecânica" for d in unit_row.disciplines)


def test_discipline_row_exposes_unit_groups_for_discipline_detail() -> None:
    """`discipline_rows[].unit_groups` alimenta a expansão de "Aderência por
    disciplina" (disciplina -> unidade -> área)."""
    entries = [
        _record(unit="Nova Mutum", civil_prev=100, civil_real=99.5),
        _record(unit="Rio Verde", civil_prev=80, civil_real=40),
    ]
    result = compute_idp_result(
        entries, 0.9, [], [],
        PeriodRange(start_year=2026, start_month=6, end_year=2026, end_month=6),
    )
    civil_row = next(r for r in result.discipline_rows if r.disciplina == "01 - Civil")
    assert {g.unit for g in civil_row.unit_groups} == {"NOVA MUTUM", "RIO VERDE"}
    rio_verde_group = next(g for g in civil_row.unit_groups if g.unit == "RIO VERDE")
    assert rio_verde_group.aderencia == pytest.approx(0.5)
    assert rio_verde_group.entries == [IdpAreaEntry(area="Pipe Rack", prev_acum=80, real_acum=40)]


def test_excluded_unit_keeps_own_unit_detail_but_drops_out_of_discipline_unit_groups() -> None:
    entries = [_record(unit="Ignorada", civil_prev=100, civil_real=50)]
    result = compute_idp_result(
        entries, 0.9, [], ["Ignorada"],
        PeriodRange(start_year=2026, start_month=6, end_year=2026, end_month=6),
    )
    unit_row = result.unit_rows[0]
    assert unit_row.excluded is True
    assert len(unit_row.disciplines) == 1  # continua detalhado no histórico da própria unidade
    civil_row = next(r for r in result.discipline_rows if r.disciplina == "01 - Civil")
    assert civil_row.unit_groups == []  # unidade excluída não entra na agregação por disciplina
