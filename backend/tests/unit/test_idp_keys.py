"""Porte de `tests/integration/idp-incremental.test.ts` (comportamento de
business key / content hash) e verificação da normalização leve
`normalized_unit_key`, deliberadamente diferente de `normalize_unit_code`."""

from __future__ import annotations

from app.modules.idp.calculations import normalized_unit_key
from app.modules.idp.keys import idp_business_key, idp_content_hash
from app.modules.idp.types import IdpAreaEntry, IdpExecutionPhase, IdpNormalizedRecord


def _record(
    *,
    unit: str = "Nova Mutum",
    rso_numero: int = 34,
    reference_month: int = 6,
    reference_source: str = "PDF_MES_REF",
    reference_adjusted: bool = False,
) -> IdpNormalizedRecord:
    return IdpNormalizedRecord(
        unit=unit, detected_unit=unit, unit_adjusted=False, rso_numero=rso_numero,
        detected_rso_numero=rso_numero, rso_adjusted=False, reference_year=2026,
        reference_month=reference_month, detected_reference_year=2026,
        detected_reference_month=reference_month,
        reference_source=reference_source, reference_original_text=None,
        reference_adjusted=reference_adjusted,
        period_start=None, period_end=None, emission_date=None, file_name="RSO 34.pdf",
        areas=["Pipe Rack"],
        disc_data={"01 - Civil": [IdpAreaEntry(area="Pipe Rack", prev_acum=100, real_acum=99.5)]},
        execucao_fases=[IdpExecutionPhase(label="Fase 1", prev_acum=53.08, real_acum=54.79)],
        raw={},
    )


def test_normalized_unit_key_is_light_not_canonical() -> None:
    """`normalized_unit_key` NÃO mapeia para a sigla canônica — diferente de
    `normalize_unit_code`. "Rio Verde" e "RVD" continuam DIFERENTES aqui,
    mesmo que `normalize_unit_code` os trate como a mesma unidade."""
    assert normalized_unit_key("Rio Verde") == "RIO VERDE"
    assert normalized_unit_key("RVD") == "RVD"
    assert normalized_unit_key("Rio Verde") != normalized_unit_key("RVD")
    assert normalized_unit_key(" Rondonópolis ") == "RONDONOPOLIS"


def test_mesmo_numero_de_rso_da_mesma_unidade_e_a_mesma_versao_logica() -> None:
    """Muda a competência (referenceMonth) mas mantém unidade+rsoNumero ->
    business key idêntico."""
    a = idp_business_key(_record(reference_month=6))
    b = idp_business_key(_record(reference_month=7, reference_source="MANUAL", reference_adjusted=True))
    assert a == b


def test_correcao_do_mesmo_rso_atualiza_em_vez_de_criar_outra_versao() -> None:
    first = _record(reference_month=6)
    corrected = _record(reference_month=7, reference_source="MANUAL", reference_adjusted=True)
    assert idp_business_key(first) == idp_business_key(corrected)
    assert idp_content_hash(first) != idp_content_hash(corrected)


def test_different_rso_numero_yields_different_business_key() -> None:
    a = idp_business_key(_record(rso_numero=34))
    b = idp_business_key(_record(rso_numero=35))
    assert a != b


def test_disc_data_change_changes_content_hash() -> None:
    a = idp_content_hash(_record())
    modified = _record()
    modified.disc_data = {"01 - Civil": [IdpAreaEntry(area="Pipe Rack", prev_acum=100, real_acum=50)]}
    b = idp_content_hash(modified)
    assert a != b
