"""Geração de businessKey e contentHash. Porte literal de `src/lib/hashing/index.ts`.

businessKey  = identidade lógica do registro (campos estáveis).
contentHash  = SHA-256 dos campos mutáveis (status, responsável, etc.).

As chaves são geradas no backend. A ordem/normalização precisa ser BIT A BIT
idêntica à implementação TypeScript — validado por testes de contrato em
`tests/contract/`.
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.shared.normalization import normalize_for_key


def build_key_string(parts: list[Any]) -> str:
    """Monta uma string de chave a partir de partes, normalizando cada uma
    (caixa alta + espaços colapsados) e unindo por "|"."""
    return "|".join(normalize_for_key(p) for p in parts)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_business_key(module: str, parts: list[Any]) -> str:
    """businessKey: hash estável da identidade lógica."""
    return module.upper() + ":" + sha256(build_key_string(parts))


def make_content_hash(mutable_fields: dict[str, Any]) -> str:
    """contentHash: hash dos campos mutáveis, chaves ordenadas para ser
    determinístico independente da ordem de inserção."""
    ordered = "|".join(
        f"{key}={normalize_for_key(mutable_fields[key])}" for key in sorted(mutable_fields)
    )
    return sha256(ordered)
