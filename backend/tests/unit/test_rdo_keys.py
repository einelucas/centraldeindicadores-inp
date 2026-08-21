"""Porte literal de `tests/unit/rdo-keys.test.ts`."""

from __future__ import annotations

from datetime import datetime

from app.modules.rdo.keys import rdo_business_key, rdo_content_hash
from app.modules.rdo.types import RdoNormalizedRecord


def _rec(disciplina: str, status: str = "Aprovado", relatorio_id: str = "R-1") -> RdoNormalizedRecord:
    return RdoNormalizedRecord(
        data_referencia=datetime(2026, 1, 5),
        empresa_nome="UNIDADE A",
        status_descricao=status,
        relatorio_id=relatorio_id,
        grupo=None,
        disciplina=disciplina,
        year=2026,
        month=1,
        raw={},
    )


def test_same_relatorio_different_disciplina_yields_different_key() -> None:
    a = rdo_business_key(_rec("Civil"))
    b = rdo_business_key(_rec("Mecânica"))
    assert a != b


def test_same_logical_identity_yields_same_key() -> None:
    a = rdo_business_key(_rec("Civil"))
    b = rdo_business_key(_rec("Civil"))
    assert a == b


def test_status_change_keeps_key_but_changes_hash() -> None:
    key_a = rdo_business_key(_rec("Civil", status="Preenchendo Relatório"))
    key_b = rdo_business_key(_rec("Civil", status="Aprovado"))
    assert key_a == key_b

    hash_a = rdo_content_hash(_rec("Civil", status="Preenchendo Relatório"))
    hash_b = rdo_content_hash(_rec("Civil", status="Aprovado"))
    assert hash_a != hash_b
