"""Business key e content hash do RDO. Porte literal de
`src/features/rdo/utils/keys.ts`.

A chave de negócio NÃO pode usar só `relatorioId` — o mesmo relatório pode
ter várias linhas por grupo/disciplina, então a chave inclui `grupo` e
`disciplina` para diferenciá-las. `statusDescricao` fica de fora da business
key de propósito: o mesmo RDO lógico (mesma data/empresa/grupo/disciplina/
relatório) que muda de status entre importações deve mapear para a mesma
`businessKey`, disparando um UPDATE em vez de um INSERT duplicado.
"""

from __future__ import annotations

from typing import Any

from app.modules.rdo.types import RdoNormalizedRecord
from app.shared.dates import to_iso_date_key
from app.shared.hashing import make_business_key, make_content_hash

__all__ = ["rdo_business_key", "rdo_content_hash"]


def _first_not_none(*values: Any) -> Any:
    """Equivalente ao `??` do JS: só cai para o próximo valor quando o
    anterior é `None` (diferente do `or` do Python, que também cairia em
    valores falsy-mas-presentes como uma string vazia)."""
    for value in values:
        if value is not None:
            return value
    return None


def rdo_business_key(record: RdoNormalizedRecord) -> str:
    """Ordem exata das partes: relatorioId | dataReferencia(ISO date) |
    empresaNome | grupo | disciplina."""
    return make_business_key(
        "RDO",
        [
            record.relatorio_id or "",
            to_iso_date_key(record.data_referencia),
            record.empresa_nome,
            record.grupo or "",
            record.disciplina or "",
        ],
    )


def rdo_content_hash(record: RdoNormalizedRecord) -> str:
    """Verifica tanto a chave sem acento (`responsavel`) quanto com acento
    (`responsável`) dentro de `raw`, pois o header original da planilha pode
    ter vindo com ou sem acentuação (Divergência #8: se a planilha usar outra
    grafia, mudanças nesses campos nunca disparam update)."""
    responsavel = _first_not_none(record.raw.get("responsavel"), record.raw.get("responsável"), "")
    observacao = _first_not_none(record.raw.get("observacao"), record.raw.get("observação"), "")
    return make_content_hash(
        {
            "statusDescricao": record.status_descricao,
            "responsavel": responsavel,
            "observacao": observacao,
        }
    )
