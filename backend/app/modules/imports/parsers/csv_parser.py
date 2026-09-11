"""Leitura de CSV no servidor. Nome do arquivo é `csv_parser.py` (não
`csv.py`) de propósito, para nunca colidir com o módulo `csv` da stdlib que
este arquivo importa.

Aceita UTF-8, UTF-8 com BOM e as codificações mais comuns em CSV exportado
pelo Excel (cp1252/latin-1). Detecta o delimitador (`,`, `;`, tab) via
`csv.Sniffer`, com fallback determinístico se a detecção falhar.
"""

from __future__ import annotations

import csv
from typing import Any

from app.modules.imports.parsers.base import FileFormatError

__all__ = ["read_csv_rows"]

_ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")
_FALLBACK_DELIMITERS = (",", ";", "\t")


def _decode(content: bytes) -> str:
    for encoding in _ENCODINGS:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise FileFormatError("Não foi possível decodificar o arquivo CSV (codificação não reconhecida).")


def _detect_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        return dialect.delimiter
    except csv.Error:
        pass
    first_line = sample.splitlines()[0] if sample.splitlines() else ""
    counts = {d: first_line.count(d) for d in _FALLBACK_DELIMITERS}
    best = max(counts, key=lambda d: counts[d])
    return best if counts[best] > 0 else ","


def read_csv_rows(content: bytes) -> list[dict[str, Any]]:
    """Lê o CSV inteiro como lista de dicts (cabeçalho = primeira linha)."""
    if not content.strip():
        return []
    text = _decode(content)
    delimiter = _detect_delimiter(text[:4096])
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    rows: list[dict[str, Any]] = []
    for row in reader:
        if all(value is None or str(value).strip() == "" for value in row.values()):
            continue
        rows.append(dict(row))
    return rows
