"""Porte literal de `tests/unit/rnc-calculations.test.ts`."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.modules.rnc.calculations import average_monthly_rnc_days, compute_rnc_result, median
from app.modules.rnc.types import RncNormalizedRecord


def _rec(
    unidade: str,
    status: str,
    *,
    year: int = 2026,
    month: int = 1,
    day: int = 5,
    data_solucao: datetime | None = None,
    tempo_tratativa: float | None = None,
    ofensor: str = "N/A",
) -> RncNormalizedRecord:
    return RncNormalizedRecord(
        status_rnc=status,
        unidade=unidade,
        data_criacao=datetime(year, month, day),
        data_solucao=data_solucao,
        tempo_tratativa=tempo_tratativa,
        ofensor=ofensor,
        year=year,
        month=month,
        raw={},
    )


def test_monthly_aggregation_and_dias_medios() -> None:
    records = [
        _rec("X", "TRATADA", month=1, data_solucao=datetime(2026, 1, 10), tempo_tratativa=7),
        _rec("X", "TRATADA", month=1, data_solucao=datetime(2026, 1, 20), tempo_tratativa=21),
    ]
    result = compute_rnc_result(records)
    jan = next(m for m in result.months if m.month == 0)
    assert jan.chamados == 2
    assert jan.solucionados == 2
    assert jan.dias_medios == pytest.approx(14)
    assert jan.dentro_meta is True  # 14 <= 15


def test_chamado_sem_solucao_nao_entra_na_media() -> None:
    records = [_rec("X", "ABERTA", month=2, data_solucao=None, tempo_tratativa=None)]
    result = compute_rnc_result(records)
    fev = next(m for m in result.months if m.month == 1)
    assert fev.chamados == 1
    assert fev.solucionados == 0
    assert fev.dias_medios is None
    assert fev.dentro_meta is None


def test_aderencia_por_unidade() -> None:
    records = [_rec("X", "TRATADA"), _rec("X", "ABERTA")]
    result = compute_rnc_result(records)
    unit_x = next(u for u in result.units if u.name == "X")
    assert unit_x.criadas == 2
    assert unit_x.tratadas == 1
    assert unit_x.aderencia == pytest.approx(0.5)


def test_ofensores_ranking() -> None:
    records = [
        _rec("X", "TRATADA", ofensor="Fornecedor"),
        _rec("X", "TRATADA", ofensor="Fornecedor"),
        _rec("X", "TRATADA", ofensor="Processo"),
    ]
    result = compute_rnc_result(records)
    top = result.ofensores[0]
    assert top.name == "Fornecedor"
    assert top.count == 2
    assert top.pct == pytest.approx(2 / 3)


def test_consolidacao_e_media_simples_dos_meses_nao_ponderada() -> None:
    records = [
        _rec("X", "TRATADA", month=6, data_solucao=datetime(2026, 6, 10), tempo_tratativa=10),
        _rec("X", "TRATADA", month=7, data_solucao=datetime(2026, 7, 10), tempo_tratativa=20),
        _rec("X", "TRATADA", month=7, data_solucao=datetime(2026, 7, 15), tempo_tratativa=20),
    ]
    result = compute_rnc_result(records)
    # Junho: 1 RNC a 10 dias. Julho: 2 RNCs a 20 dias cada.
    # resultadoDias = (10 + 20) / 2 = 15, NAO a ponderada (10+20+20)/3 ~= 16.67.
    assert result.resultado_dias == pytest.approx(15)


def test_caso_6_calculo_mensal_individual_inalterado() -> None:
    records = [
        _rec("X", "TRATADA", month=6, data_solucao=datetime(2026, 6, day), tempo_tratativa=28.5)
        for day in range(1, 15)
    ]
    result = compute_rnc_result(records)
    jun = next(m for m in result.months if m.month == 5)
    assert jun.chamados == 14
    assert jun.solucionados == 14
    assert jun.dias_medios == pytest.approx(28.5)


def test_evidencias_por_unidade() -> None:
    records = [
        _rec("X", "TRATADA", data_solucao=datetime(2026, 1, 10), tempo_tratativa=10, ofensor="Fornecedor"),
        _rec("X", "TRATADA", data_solucao=datetime(2026, 1, 11), tempo_tratativa=30, ofensor="Fornecedor"),
        _rec("X", "TRATADA", data_solucao=datetime(2026, 1, 12), tempo_tratativa=20, ofensor="Execução"),
    ]
    result = compute_rnc_result(records)
    unit_x = next(u for u in result.units if u.name == "X")
    assert unit_x.dias_medios == pytest.approx(20)  # (10+30+20)/3
    assert unit_x.dias_medianos == pytest.approx(20)  # mediana de [10,20,30]
    assert unit_x.maior_tempo_tratativa == pytest.approx(30)
    assert unit_x.tratativas_com_tempo == 3
    assert unit_x.principal_ofensor == "Fornecedor"
    assert unit_x.principal_ofensor_count == 2


class TestAverageMonthlyRncDays:
    def test_caso_1(self) -> None:
        assert average_monthly_rnc_days([28.5, 11.3]) == pytest.approx(19.9)

    def test_caso_2_meses_sem_resultado_nao_entram_no_denominador(self) -> None:
        assert average_monthly_rnc_days([20, None, 10]) == pytest.approx(15)  # (20+10)/2, nao /3

    def test_caso_3_um_mes(self) -> None:
        assert average_monthly_rnc_days([17.4]) == pytest.approx(17.4)

    def test_caso_4_todos_nulos_ou_vazio(self) -> None:
        assert average_monthly_rnc_days([None, None]) is None
        assert average_monthly_rnc_days([]) is None

    def test_caso_5_nao_e_ponderado_por_volume(self) -> None:
        assert average_monthly_rnc_days([10, 30]) == pytest.approx(20)


def test_cenario_oficial_de_validacao_nao_e_a_formula_ponderada_antiga() -> None:
    records = [
        _rec("X", "TRATADA", month=6, data_solucao=datetime(2026, 6, day), tempo_tratativa=28.5)
        for day in range(1, 15)
    ] + [
        _rec("X", "TRATADA", month=7, data_solucao=datetime(2026, 7, day), tempo_tratativa=11.3)
        for day in range(1, 11)
    ]
    result = compute_rnc_result(records)
    assert result.resultado_dias == pytest.approx(19.9, abs=1e-9)
    assert result.resultado_dias != pytest.approx(21.3, abs=0.5)


def test_median_even_and_odd() -> None:
    assert median([10, 20, 30]) == 20
    assert median([10, 20, 30, 40]) == pytest.approx(25)
    assert median([]) is None


def test_unidade_excluida_permanece_na_tabela_mas_sai_dos_totais() -> None:
    records = [_rec("Ignorada", "TRATADA"), _rec("Valida", "TRATADA")]
    result = compute_rnc_result(records, excluded_units=["Ignorada"])
    assert result.total_criadas == 1
    ignorada = next(u for u in result.units if u.name == "IGNORADA")
    assert ignorada.excluded is True
    assert ignorada.criadas == 1


def test_periodo_e_corte_estrutural_remove_de_toda_agregacao() -> None:
    from app.shared.period import PeriodRange

    records = [
        _rec("X", "TRATADA", year=2026, month=3),
        _rec("X", "TRATADA", year=2026, month=12),
    ]
    period = PeriodRange(start_year=2026, start_month=1, end_year=2026, end_month=6)
    result = compute_rnc_result(records, period=period)
    assert result.total_criadas == 1
    assert all(u.criadas == 1 for u in result.units)
