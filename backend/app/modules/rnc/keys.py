"""Business key e content hash do RNC. Porte literal de
`src/features/rnc/utils/keys.ts`.

A `businessKey` inclui um desambiguador opcional lido de `raw["descrição"]`/
`raw["descricao"]` (Divergência #9 do inventário): essa coluna NÃO é
obrigatória na planilha de origem — se ausente, o desambiguador vira sempre
"" e duas RNCs genuinamente diferentes com mesma unidade+data de criação+
ofensor colidem na mesma chave (a segunda vira `update`/`ignored` da
primeira, nunca um registro novo). Risco herdado do comportamento original,
preservado por paridade.
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
    """Ordem exata das partes: unidade | dataCriacao(ISO date) | ofensor |
    descrição/observação (opcional, lida de `raw`)."""
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
