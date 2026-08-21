"""Testes do gerador de sugestão de justificativa do RDO
(`app/modules/justifications/generators/rdo.py`), porte de
`src/features/justifications/generators/rdo.ts`."""

from __future__ import annotations

from datetime import datetime

from app.modules.justifications.generators.rdo import generate_rdo_justification
from app.modules.rdo.types import RdoNormalizedRecord


def _rec(
    status: str, empresa: str = "UNIDADE A", grupo: str | None = "Mecânica",
    disciplina: str | None = "Tubulação",
) -> RdoNormalizedRecord:
    return RdoNormalizedRecord(
        data_referencia=datetime(2027, 3, 5), empresa_nome=empresa, status_descricao=status,
        relatorio_id="R1", grupo=grupo, disciplina=disciplina, year=2027, month=3, raw={},
    )


def test_no_data_when_no_records() -> None:
    suggestion = generate_rdo_justification(
        records=[], previous_records=[], year=2027, month=3, threshold=0.8,
        excluded_units=[], source_import=None,
    )
    assert suggestion.status == "NO_DATA"
    assert suggestion.result is None
    assert suggestion.evidence == []
    assert "Não há RDOs válidos" in suggestion.suggested_text


def test_below_target_with_pending_ranking() -> None:
    records = [
        _rec("Aprovado"),
        _rec("Revisar Relatório"),
        _rec("Preenchendo Relatório"),
        _rec("Revisar Relatório", empresa="UNIDADE B", grupo="Civil", disciplina="Estrutura"),
    ]
    suggestion = generate_rdo_justification(
        records=records, previous_records=[], year=2027, month=3, threshold=0.8,
        excluded_units=[], source_import=None,
    )
    assert suggestion.status == "BELOW_TARGET"
    assert suggestion.result == 0.25  # 1 aprovado de 4
    assert any(e.label == "Maior concentração" for e in suggestion.evidence)
    assert "UNIDADE A" in suggestion.suggested_text


def test_on_target_exact_meta() -> None:
    records = [_rec("Aprovado"), _rec("Aprovado"), _rec("Revisar Relatório"), _rec("Aprovado")]
    suggestion = generate_rdo_justification(
        records=records, previous_records=[], year=2027, month=3, threshold=0.75,
        excluded_units=[], source_import=None,
    )
    assert suggestion.status == "ON_TARGET"  # 0.75 >= 0.75


def test_previous_month_adds_variation_evidence() -> None:
    records = [_rec("Aprovado"), _rec("Revisar Relatório")]
    previous_records = [_rec("Aprovado"), _rec("Aprovado")]
    suggestion = generate_rdo_justification(
        records=records, previous_records=previous_records, year=2027, month=3, threshold=0.8,
        excluded_units=[], source_import=None,
    )
    assert any(e.label == "Variação mensal" for e in suggestion.evidence)
    assert "mês anterior" in suggestion.suggested_text


def test_excluded_units_are_filtered_out() -> None:
    records = [_rec("Revisar Relatório", empresa="Ignorada"), _rec("Aprovado", empresa="Valida")]
    suggestion = generate_rdo_justification(
        records=records, previous_records=[], year=2027, month=3, threshold=0.8,
        excluded_units=["Ignorada"], source_import=None,
    )
    assert suggestion.result == 1.0  # só "Valida" conta, aprovada
