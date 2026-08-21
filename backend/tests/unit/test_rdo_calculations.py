"""Porte literal de `tests/unit/rdo-calculations.test.ts`."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.modules.rdo.calculations import calculate_rdo_adherence, compute_rdo_result, meets_target
from app.modules.rdo.types import RDO_DEFAULT_TARGET, RdoNormalizedRecord


def _rec(
    empresa: str,
    status: str,
    year: int = 2026,
    month: int = 1,
    day: int = 5,
    relatorio_id: str | None = None,
) -> RdoNormalizedRecord:
    return RdoNormalizedRecord(
        data_referencia=datetime(year, month, day),
        empresa_nome=empresa,
        status_descricao=status,
        relatorio_id=relatorio_id,
        grupo=None,
        disciplina=None,
        year=year,
        month=month,
        raw={},
    )


def test_calculate_rdo_adherence_basic() -> None:
    assert calculate_rdo_adherence(76, 100) == pytest.approx(0.76)


def test_calculate_rdo_adherence_division_by_zero() -> None:
    assert calculate_rdo_adherence(1, 0) == 0


def test_rdo_default_target_is_08() -> None:
    assert RDO_DEFAULT_TARGET == 0.8


def test_record_without_unit_is_ignored() -> None:
    records = [_rec("UNIDADE A", "Aprovado"), _rec("", "Aprovado")]
    result = compute_rdo_result(records)
    assert result.total_emitidos == 1


def test_status_breakdown() -> None:
    records = [
        _rec("UNIDADE A", "Aprovado"),
        _rec("UNIDADE A", "Aprovado"),
        _rec("UNIDADE A", "Revisar Relatório"),
        _rec("UNIDADE A", "Preenchendo Relatório"),
    ]
    result = compute_rdo_result(records)
    assert result.total_emitidos == 4
    assert result.total_aprovados == 2
    assert result.total_revisar == 1
    assert result.total_preenchendo == 1


def test_unit_and_month_aggregation() -> None:
    records = [
        _rec("A", "Aprovado", month=1, day=2),
        _rec("A", "Aprovado", month=2, day=2),
        _rec("B", "Revisar Relatório", month=1, day=2),
    ]
    result = compute_rdo_result(records)
    assert len(result.units) == 2
    assert len(result.months) == 2
    unit_a = next(u for u in result.units if u.name == "A")
    assert unit_a.emitidos == 2
    assert unit_a.aprovados == 2


def test_meets_target() -> None:
    assert meets_target(0.8, 0.8) is True
    assert meets_target(0.7, 0.8) is False


def test_excluded_unit_stays_in_by_unit_table_but_not_totals() -> None:
    records = [_rec("Ignorada", "Aprovado"), _rec("Valida", "Aprovado")]
    result = compute_rdo_result(records, excluded_units=["Ignorada"])
    assert result.total_emitidos == 1
    names = {u.name for u in result.units}
    assert "IGNORADA" in names or "Ignorada".upper() in {n.upper() for n in names}


def test_other_status_text_does_not_increment_breakdowns() -> None:
    records = [_rec("A", "Outro Status Qualquer")]
    result = compute_rdo_result(records)
    assert result.total_emitidos == 1
    assert result.total_aprovados == 0
    assert result.total_revisar == 0
    assert result.total_preenchendo == 0
