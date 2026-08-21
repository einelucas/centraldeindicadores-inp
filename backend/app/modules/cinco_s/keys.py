"""Chaves do 5S. Porte literal de `src/features/cinco-s/utils/keys.ts`.

businessKey (identidade lógica):
    unit + year + month (uma auditoria por unidade/mês)

contentHash (campos mutáveis):
    as áreas (divisao/area/meta/nota) — se a auditoria for corrigida e
    reenviada, o hash muda e o registro é atualizado.

Nota de paridade (ver `inventory-cinco-s.md`, divergência #7): o TS monta o
hash com `String(array)` sobre o array já ordenado de strings de área — em
JS isso produz um `Array.prototype.join(",")`, e não uma serialização JSON
campo a campo. Aqui replicamos esse detalhe explicitamente (join manual por
vírgula, sem espaços) para que o formato de entrada do hash seja idêntico ao
original, inclusive a forma como `meta`/`nota` numéricos são convertidos
para texto (`Number.prototype.toString()` do JS não imprime `.0` para
valores inteiros, ao contrário do `str()` de um `float` em Python).
"""

from __future__ import annotations

import math

from app.modules.cinco_s.types import FiveSNormalizedRecord
from app.shared.hashing import make_business_key, make_content_hash
from app.shared.units import normalize_unit_code


def _js_number_string(value: float) -> str:
    """Aproxima `Number.prototype.toString()` do JS: inteiros sem `.0`,
    fracionários com a representação mínima do Python (equivalente na
    prática para os valores de nota/meta usados no 5S)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    if value.is_integer():
        return str(int(value))
    return repr(value)


def five_s_business_key(record: FiveSNormalizedRecord) -> str:
    return make_business_key(
        "5S",
        [normalize_unit_code(record.unit), str(record.year), str(record.month)],
    )


def five_s_content_hash(record: FiveSNormalizedRecord) -> str:
    # Ordena as áreas para o hash ser estável independente da ordem de leitura.
    area_strings = sorted(
        f"{area.divisao or ''}|{area.area}|{_js_number_string(area.meta)}|{_js_number_string(area.nota)}"
        for area in record.areas
    )
    joined = ",".join(area_strings)
    return make_content_hash({"areas": joined})
