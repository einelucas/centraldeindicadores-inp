"""Porte de `tests/unit/cinco-s-calculations.test.ts`."""

from __future__ import annotations

from app.modules.cinco_s.calculations import aderencia_area, aderencia_unidade, compute_five_s_result
from app.modules.cinco_s.types import FiveSArea, FiveSNormalizedRecord


def test_aderencia_area_clamped_at_100_percent() -> None:
    area = FiveSArea(divisao="D1", area="A1", meta=0.8, nota=1.0)
    assert aderencia_area(area) == 1.0


def test_aderencia_area_zero_meta_is_zero() -> None:
    area = FiveSArea(divisao=None, area="A1", meta=0, nota=0.5)
    assert aderencia_area(area) == 0.0


def test_aderencia_unidade_simple_average() -> None:
    areas = [
        FiveSArea(divisao=None, area="A1", meta=1.0, nota=0.8),
        FiveSArea(divisao=None, area="A2", meta=1.0, nota=1.0),
    ]
    assert aderencia_unidade(areas) == 0.9


def _rec(unit: str, year: int, month: int, notas: list[float]) -> FiveSNormalizedRecord:
    areas = [FiveSArea(divisao=None, area=f"A{i}", meta=1.0, nota=n) for i, n in enumerate(notas)]
    return FiveSNormalizedRecord(unit=unit, year=year, month=month, areas=areas, raw={})


def test_consolidated_average_excludes_configured_units_without_zeroing() -> None:
    records = [
        _rec("LEM", 2027, 3, [1.0]),
        _rec("MTU", 2027, 3, [0.5]),
        _rec("SP", 2027, 3, [0.0]),  # excluída por padrão
    ]
    result = compute_five_s_result(records, excluded=["SP"])
    month = result.months[-1]
    # média de LEM(1.0) e MTU(0.5) apenas — SP não entra no numerador nem denominador
    assert month.geral == 0.75
    assert month.units_count == 2


def test_current_result_never_falls_back_to_earlier_month() -> None:
    records = [
        _rec("LEM", 2027, 3, [1.0]),
        _rec("SP", 2027, 4, [0.0]),  # único registro do mês seguinte é de unidade excluída
    ]
    result = compute_five_s_result(records, excluded=["SP"])
    # último mês (abril) não tem unidades elegíveis -> geral None, mesmo com março disponível
    assert result.latest_month == 4
    assert result.geral is None
