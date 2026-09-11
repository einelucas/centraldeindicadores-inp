"""Leitura de planilhas Excel no servidor — substitui o `xlsx` (SheetJS) que
rodava no navegador. Dispatcha pela extensão REAL do arquivo (já validada
por `signatures.py`), não por suposição:

- `.xlsx`/`.xlsm`/`.xltx` -> `openpyxl`, `read_only=True` (streaming, não
  carrega o workbook inteiro na memória).
- `.xls`/`.xlt` (legado, OLE2/BIFF) -> `xlrd` (única lib que ainda lê esse
  formato; `xlrd` 2.x deliberadamente não lê mais xlsx).
- `.xlsb` (binário) -> `pyxlsb`.

Sempre lê só a PRIMEIRA aba, primeira linha = cabeçalho — mesmo contrato do
`readWorkbookFile()`/`sheet_to_json()` (SheetJS) que o importador do
navegador usava.
"""

from __future__ import annotations

import io
from datetime import date, datetime
from typing import Any

import openpyxl
import xlrd
from pyxlsb import open_workbook as open_xlsb_workbook

from app.modules.imports.parsers.base import FileFormatError

__all__ = ["read_excel_matrix", "read_excel_rows"]

_XLSX_LIKE = {"xlsx", "xlsm", "xltx"}
_XLS_LIKE = {"xls", "xlt"}


def read_excel_rows(content: bytes, extension: str) -> list[dict[str, Any]]:
    """Lê a primeira aba como lista de dicts (cabeçalho = primeira linha),
    equivalente a `sheet_to_json(sheet, {defval: null, raw: true})` do
    SheetJS com `cellDates: true` na leitura do workbook."""
    return _rows_to_dicts(read_excel_matrix(content, extension))


def read_excel_matrix(content: bytes, extension: str) -> list[tuple[Any, ...]]:
    """Lê a primeira aba preservando todas as linhas e posições de coluna.

    Parsers com cabeçalho variável usam a matriz para localizar o cabeçalho
    real. O caminho tradicional continua usando :func:`read_excel_rows`.
    """
    if extension in _XLSX_LIKE:
        return _read_xlsx_matrix(content)
    if extension in _XLS_LIKE:
        return _read_xls_matrix(content)
    if extension == "xlsb":
        return _read_xlsb_matrix(content)
    raise FileFormatError(f"Extensão .{extension} não é um formato de planilha suportado.")


def _rows_to_dicts(rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    header = [("" if cell is None else str(cell)) for cell in rows[0]]
    out: list[dict[str, Any]] = []
    for raw_row in rows[1:]:
        if all(cell is None for cell in raw_row):
            continue
        row: dict[str, Any] = {}
        for index, key in enumerate(header):
            row[key] = raw_row[index] if index < len(raw_row) else None
        out.append(row)
    return out


def _read_xlsx_matrix(content: bytes) -> list[tuple[Any, ...]]:
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 — qualquer falha de parsing vira erro de formato
        raise FileFormatError(f"Não foi possível ler o arquivo Excel: {exc}") from exc
    try:
        sheet = workbook.worksheets[0]
        rows = [tuple(row) for row in sheet.iter_rows(values_only=True)]
    finally:
        workbook.close()
    return rows


def _read_xls_matrix(content: bytes) -> list[tuple[Any, ...]]:
    try:
        book = xlrd.open_workbook(file_contents=content)
    except Exception as exc:  # noqa: BLE001
        raise FileFormatError(f"Não foi possível ler o arquivo Excel legado: {exc}") from exc
    sheet = book.sheet_by_index(0)
    rows: list[tuple[Any, ...]] = []
    for row_index in range(sheet.nrows):
        values: list[Any] = []
        for cell in sheet.row(row_index):
            values.append(_xls_cell_value(cell, book.datemode))
        rows.append(tuple(values))
    return rows


def _xls_cell_value(cell: xlrd.sheet.Cell, datemode: int) -> Any:
    if cell.ctype == xlrd.XL_CELL_DATE:
        parts = xlrd.xldate.xldate_as_tuple(cell.value, datemode)
        year, month, day, hour, minute, second = parts
        if (hour, minute, second) == (0, 0, 0):
            return date(year, month, day)
        return datetime(year, month, day, hour, minute, second)
    if cell.ctype == xlrd.XL_CELL_EMPTY:
        return None
    return cell.value


def _read_xlsb_matrix(content: bytes) -> list[tuple[Any, ...]]:
    try:
        with open_xlsb_workbook(io.BytesIO(content)) as workbook:
            sheet_name = workbook.sheets[0]
            with workbook.get_sheet(sheet_name) as sheet:
                rows = [tuple(cell.v for cell in row) for row in sheet.rows()]
    except FileFormatError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise FileFormatError(f"Não foi possível ler o arquivo .xlsb: {exc}") from exc
    return rows
