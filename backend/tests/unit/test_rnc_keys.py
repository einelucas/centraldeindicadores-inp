"""Porte de conceitos-chave de `src/features/rnc/utils/keys.ts` — não há
suíte TS dedicada a este arquivo, mas seu comportamento é testado
indiretamente por `tests/integration/rnc-incremental.test.ts` (reimportar =
ignora; alterar tempo/data de solução = atualiza)."""

from __future__ import annotations

from datetime import datetime

from app.modules.rnc.keys import rnc_business_key, rnc_content_hash
from app.modules.rnc.types import RncNormalizedRecord


def _rec(
    ofensor: str = "Fornecedor",
    status: str = "ABERTA",
    data_solucao: datetime | None = None,
    tempo_tratativa: float | None = None,
    raw: dict | None = None,
) -> RncNormalizedRecord:
    return RncNormalizedRecord(
        status_rnc=status,
        unidade="UNIDADE A",
        data_criacao=datetime(2026, 1, 5),
        data_solucao=data_solucao,
        tempo_tratativa=tempo_tratativa,
        ofensor=ofensor,
        year=2026,
        month=1,
        raw=raw or {},
    )


def test_same_logical_identity_yields_same_key() -> None:
    a = rnc_business_key(_rec())
    b = rnc_business_key(_rec())
    assert a == b


def test_different_ofensor_yields_different_key() -> None:
    a = rnc_business_key(_rec(ofensor="Fornecedor"))
    b = rnc_business_key(_rec(ofensor="Processo"))
    assert a != b


def test_descricao_from_raw_disambiguates_business_key() -> None:
    a = rnc_business_key(_rec(raw={"descrição": "Vazamento na linha 1"}))
    b = rnc_business_key(_rec(raw={"descrição": "Vazamento na linha 2"}))
    assert a != b


def test_descricao_missing_key_falls_back_to_descricao_without_accent() -> None:
    a = rnc_business_key(_rec(raw={"descricao": "Sem acento"}))
    b = rnc_business_key(_rec(raw={"descrição": "Sem acento"}))
    assert a == b


def test_status_change_keeps_key_but_changes_hash() -> None:
    key_a = rnc_business_key(_rec(status="ABERTA"))
    key_b = rnc_business_key(_rec(status="TRATADA"))
    assert key_a == key_b

    hash_a = rnc_content_hash(_rec(status="ABERTA"))
    hash_b = rnc_content_hash(_rec(status="TRATADA"))
    assert hash_a != hash_b


def test_tempo_tratativa_change_changes_content_hash() -> None:
    hash_a = rnc_content_hash(_rec(tempo_tratativa=10))
    hash_b = rnc_content_hash(_rec(tempo_tratativa=22))
    assert hash_a != hash_b


def test_tempo_tratativa_integer_valued_float_matches_js_number_tostring() -> None:
    """`tempoTratativa=10.0` deve gerar o MESMO hash que `tempoTratativa=10`
    — em JS `String(10)` é `"10"` independente de o número ter vindo de uma
    divisão inteira ou não; `str(10.0)` do Python produziria `"10.0"` se não
    tratado (ver `_js_number_string`)."""
    hash_a = rnc_content_hash(_rec(tempo_tratativa=10))
    hash_b = rnc_content_hash(_rec(tempo_tratativa=10.0))
    assert hash_a == hash_b


def test_unidade_and_data_criacao_do_not_affect_content_hash() -> None:
    """`unidade`/`dataCriacao`/`ofensor` compõem a identidade (business key),
    não os campos mutáveis do content hash."""
    rec_a = _rec()
    rec_b = RncNormalizedRecord(
        status_rnc=rec_a.status_rnc,
        unidade="OUTRA UNIDADE",
        data_criacao=datetime(2027, 6, 1),
        data_solucao=rec_a.data_solucao,
        tempo_tratativa=rec_a.tempo_tratativa,
        ofensor="Outro Ofensor",
        year=2027,
        month=6,
        raw={},
    )
    assert rnc_content_hash(rec_a) == rnc_content_hash(rec_b)
