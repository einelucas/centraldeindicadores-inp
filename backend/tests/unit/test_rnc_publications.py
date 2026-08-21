"""Porte literal de `tests/unit/rnc-publication.test.ts`."""

from __future__ import annotations

import pytest

from app.core.errors import DomainError
from app.modules.rnc.publications import to_rnc_published_payload
from app.modules.rnc.types import RncMonthAggregate, RncOfensorAggregate, RncResult, RncUnitAggregate


def _unit(name: str, aderencia: float, excluded: bool = False) -> RncUnitAggregate:
    return RncUnitAggregate(
        name=name, criadas=6, tratadas=5, aderencia=aderencia, tempos_tratativa=[],
        dias_medios=None, dias_medianos=None, tratativas_com_tempo=0, maior_tempo_tratativa=None,
        principal_ofensor=None, principal_ofensor_count=0, excluded=excluded,
    )


def test_preserva_formato_publicado_sem_criar_meses() -> None:
    result = RncResult(
        meta_dias=15,
        excluded_units=[],
        period=None,
        total_criadas=20,
        total_tratadas=18,
        aderencia_total=0.9,
        resultado_dias=12.4,
        months=[
            RncMonthAggregate(
                year=2026, month=5, label="Jun/2026", chamados=10, solucionados=9,
                dias_medios=10.2, dentro_meta=True,
            ),
            RncMonthAggregate(
                year=2026, month=6, label="Jul/2026", chamados=10, solucionados=9,
                dias_medios=13.7, dentro_meta=True,
            ),
        ],
        units=[_unit("INPASA Sinop", 5 / 6)],
        ofensores=[
            RncOfensorAggregate(name="A", count=5, pct=0.5),
            RncOfensorAggregate(name="B", count=2, pct=0.2),
            RncOfensorAggregate(name="C", count=1, pct=0.1),
            RncOfensorAggregate(name="D", count=1, pct=0.1),
        ],
    )

    payload = to_rnc_published_payload(result)

    assert payload["resultado"] == pytest.approx(12.4)  # sem arredondar
    assert payload["unidades"][0] == {"n": "Sinop", "v": 83}
    assert payload["mensal"] == [
        {"label": "Jun/2026", "v": pytest.approx(10.2)},
        {"label": "Jul/2026", "v": pytest.approx(13.7)},
    ]
    assert payload["ofensores"][-1] == {"n": "Outros", "pct": pytest.approx(10.0)}
    assert payload["pontos"] == 1158.2
    assert payload["peso"] == 0.1


def test_nao_arredonda_valor_acima_da_meta_para_dentro_da_meta() -> None:
    result = RncResult(
        meta_dias=15,
        excluded_units=[],
        period=None,
        total_criadas=1,
        total_tratadas=1,
        aderencia_total=1.0,
        resultado_dias=15.04,
        months=[
            RncMonthAggregate(
                year=2026, month=5, label="Jun/2026", chamados=1, solucionados=1,
                dias_medios=15.04, dentro_meta=False,
            ),
        ],
        units=[],
        ofensores=[],
    )

    payload = to_rnc_published_payload(result)

    assert payload["mensal"] == [{"label": "Jun/2026", "v": pytest.approx(15.04)}]


def test_nao_permite_publicacao_sem_tempo_de_tratativa_real() -> None:
    result = RncResult(
        meta_dias=15,
        excluded_units=[],
        period=None,
        total_criadas=1,
        total_tratadas=0,
        aderencia_total=0.0,
        resultado_dias=None,
        months=[],
        units=[],
        ofensores=[],
    )

    with pytest.raises(DomainError, match=r"(?i)tempo de tratativa"):
        to_rnc_published_payload(result)
