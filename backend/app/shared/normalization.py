"""Normalização de dados importados. Porte literal de `src/lib/normalization/index.ts`."""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")


def collapse_spaces(value: str) -> str:
    """Colapsa espaços e apara as pontas."""
    return _WHITESPACE_RE.sub(" ", value).strip()


def norm_header(header: object) -> str:
    """Normaliza um cabeçalho de coluna: minúsculas, espaços viram underscore."""
    text = "" if header is None else str(header)
    return _WHITESPACE_RE.sub("_", text.strip().lower())


def normalize_rows(raw_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Aplica `norm_header` a todas as chaves de cada linha bruta."""
    return [{norm_header(key): row[key] for key in row} for row in raw_rows]


def normalize_for_key(value: object) -> str:
    """Normaliza texto para COMPARAÇÃO em business keys: caixa alta, espaços
    colapsados. Preserva acentos de propósito."""
    if value is None:
        return ""
    return collapse_spaces(str(value)).upper()


_ACCENT_RE = re.compile(r"[̀-ͯ]")
_NON_ALNUM_RE = re.compile(r"[^A-Z0-9 ]")


def normalize_for_match(value: object) -> str:
    """Normalização "exata" para matching de nomes: remove acentos, pontuação
    leve e caixa. Usada apenas em busca fuzzy, nunca como identidade única."""
    text = collapse_spaces(str(value) if value is not None else "").upper()
    text = unicodedata.normalize("NFD", text)
    text = _ACCENT_RE.sub("", text)
    text = _NON_ALNUM_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def null_if_empty(value: object) -> str | None:
    """Converte string vazia, "-", None em None; caso contrário retorna trim."""
    if value is None:
        return None
    text = str(value).strip()
    if text in ("", "-"):
        return None
    return text
