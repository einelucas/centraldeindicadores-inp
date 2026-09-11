"""Business key e content hash do RNC.

Exportações atuais fornecem ``Item ID (auto generated)``, que é a identidade
estável prioritária. Planilhas antigas sem esse campo continuam usando a
composição legada de unidade, data de criação, ofensor e descrição.
"""

from __future__ import annotations

import math
from typing import Any

from app.modules.rnc.types import RncNormalizedRecord
from app.shared.dates import to_iso_date_key
from app.shared.hashing import make_business_key, make_content_hash

__all__ = ["rnc_business_key", "rnc_content_hash"]


def _first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _js_number_string(value: float) -> str:
    """Aproxima `Number.prototype.toString()` do JS: inteiros sem `.0`
    (`10.0` -> `"10"`), fracionários com a representação mínima do Python.
    Necessário para que `tempoTratativa` produza o mesmo `contentHash` que o
    TypeScript original (`String(10)` !== Python `str(10.0)`)."""
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    if value.is_integer():
        return str(int(value))
    return repr(value)


def rnc_business_key(record: RncNormalizedRecord) -> str:
    """Usa Item ID quando disponível e preserva o fallback legado."""
    item_id = _first_not_none(
        record.raw.get("item_id_auto_generated"),
        record.raw.get("item id (auto generated)"),
    )
    if item_id not in (None, ""):
        return make_business_key("RNC", ["ITEM", item_id])

    descricao = _first_not_none(record.raw.get("descrição"), record.raw.get("descricao"), "")
    return make_business_key(
        "RNC",
        [
            record.unidade,
            to_iso_date_key(record.data_criacao),
            record.ofensor,
            str(descricao),
        ],
    )


def rnc_content_hash(record: RncNormalizedRecord) -> str:
    """Campos mutáveis: statusRnc + dataSolucao + tempoTratativa. `unidade`,
    `dataCriacao`, `ofensor` e `raw` compõem a identidade (business key) e
    nunca disparam `update` sozinhos."""
    return make_content_hash(
        {
            "statusRnc": record.status_rnc,
            "dataSolucao": to_iso_date_key(record.data_solucao) if record.data_solucao else "",
            "tempoTratativa": (
                _js_number_string(record.tempo_tratativa) if record.tempo_tratativa is not None else ""
            ),
        }
    )
