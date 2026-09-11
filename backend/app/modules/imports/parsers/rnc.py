"""Parser de planilhas RNC executado no servidor.

Mantém as regras do importador legado: valida as seis colunas obrigatórias,
remove somente linhas integralmente duplicadas e converte cada linha para o
contrato ``RncRecordIn`` antes do upsert incremental.
"""

from __future__ import annotations

import math
import re
import unicodedata
from datetime import date, datetime
from typing import Any

from app.modules.imports.parsers.base import FileParseResult
from app.modules.imports.parsers.csv_parser import read_csv_rows
from app.modules.imports.parsers.excel import read_excel_matrix
from app.modules.imports.parsers.signatures import assert_valid_signature, extension_of
from app.modules.imports.registry import FileRowError
from app.shared.dates import parse_flex_date
from app.shared.normalization import normalize_rows
from app.shared.units import normalize_unit_code

__all__ = ["dedupe_rnc_rows", "parse_rnc_file", "to_rnc_record"]

REQUIRED_RNC_COLS = (
    "status_rnc",
    "unidade",
    "data_de_criacao",
    "data_de_solucao",
    "tempo_de_tratativa",
    "ofensor",
)


def _canonical_header(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value))
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = re.sub(r"[^a-z0-9_]+", "_", text.lower())
    return re.sub(r"_+", "_", text).strip("_")


def parse_rnc_file(content: bytes, filename: str) -> FileParseResult:
    extension = extension_of(filename)
    assert_valid_signature(content, extension)

    if extension == "csv":
        raw_rows = read_csv_rows(content)
        rows = _canonicalize_rows(normalize_rows(raw_rows))
    else:
        rows = _rows_after_detected_header(read_excel_matrix(content, extension))

    result = FileParseResult(file_name=filename, found=len(rows))
    if not rows:
        return result

    sample_keys = set().union(*(row.keys() for row in rows))
    missing = [column for column in REQUIRED_RNC_COLS if column not in sample_keys]
    if missing:
        result.errors.append(
            FileRowError(row=None, field=None, message=f"Faltam colunas: {', '.join(missing)}.")
        )
        return result

    result.rows = rows
    return result


def _canonicalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{_canonical_header(key): value for key, value in row.items()} for row in rows]


def _rows_after_detected_header(matrix: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    """Localiza o cabeçalho real nas primeiras linhas da primeira aba."""
    required = set(REQUIRED_RNC_COLS)
    header_index: int | None = None
    headers: list[str] = []
    for index, matrix_row in enumerate(matrix[:50]):
        candidate = [_canonical_header(value) for value in matrix_row]
        if required.issubset(candidate):
            header_index = index
            headers = candidate
            break

    if header_index is None:
        # Mantém o diagnóstico de colunas faltantes no chamador.
        return _canonicalize_rows(normalize_rows(_matrix_first_row_as_header(matrix)))

    parsed: list[dict[str, Any]] = []
    for values in matrix[header_index + 1 :]:
        if all(value in (None, "") for value in values):
            continue
        parsed_row = {
            header: values[column] if column < len(values) else None
            for column, header in enumerate(headers)
            if header
        }
        # Exportações podem terminar com uma linha de média/total apenas na
        # coluna de tempo. Ela não representa uma RNC.
        if all(
            parsed_row.get(field) in (None, "")
            for field in ("status_rnc", "unidade", "data_de_criacao")
        ):
            continue
        parsed.append(parsed_row)
    return parsed


def _matrix_first_row_as_header(matrix: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    if not matrix:
        return []
    headers = [str(value) if value is not None else "" for value in matrix[0]]
    return [
        {
            header: values[column] if column < len(values) else None
            for column, header in enumerate(headers)
            if header
        }
        for values in matrix[1:]
        if any(value not in (None, "") for value in values)
    ]


def dedupe_rnc_rows(all_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    if not all_rows:
        return [], 0

    columns = sorted({column for row in all_rows for column in row})
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    duplicates = 0
    for row in all_rows:
        parts: list[str] = []
        for column in columns:
            value = row.get(column)
            if isinstance(value, datetime | date):
                parts.append(value.isoformat())
            else:
                parts.append(str(value))
        signature = "|".join(parts)
        if signature in seen:
            duplicates += 1
            continue
        seen.add(signature)
        rows.append(row)
    return rows, duplicates


def _parse_br_number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        number = float(value)
        return number if math.isfinite(number) else None
    text = str(value).strip()
    if not text or text == "-" or text.upper() == "NAN":
        return None
    try:
        number = float(text.replace(".", "").replace(",", "."))
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def to_rnc_record(row: dict[str, Any]) -> dict[str, Any] | None:
    data_criacao = parse_flex_date(row.get("data_de_criacao"))
    if data_criacao is None:
        return None

    raw_solution = row.get("data_de_solucao")
    data_solucao = None if raw_solution in (None, "") else parse_flex_date(raw_solution)

    return {
        "statusRnc": str(row.get("status_rnc") or "").strip(),
        "unidade": normalize_unit_code(row.get("unidade")),
        "dataCriacao": data_criacao.isoformat(),
        "dataSolucao": data_solucao.isoformat() if data_solucao else None,
        "tempoTratativa": _parse_br_number(row.get("tempo_de_tratativa")),
        "ofensor": str(row.get("ofensor") or "").strip() or "N/A",
        "year": data_criacao.year,
        "month": data_criacao.month,
        "raw": {key: _json_safe(value) for key, value in row.items()},
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value
