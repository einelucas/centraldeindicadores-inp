"""Testes de `app/modules/imports/parsers/excel.py` — xlsx (openpyxl) e xls
legado (xlrd). Os workbooks de teste são gerados em memória (nunca fixtures
binárias versionadas), cobrindo datas nativas do Excel e cabeçalho na
primeira linha."""

from __future__ import annotations

import io
from datetime import date, datetime

import openpyxl
import pytest
import xlwt

from app.modules.imports.parsers.base import FileFormatError
from app.modules.imports.parsers.excel import read_excel_rows


def _build_xlsx(rows: list[list[object]]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _build_xls(rows: list[list[object]]) -> bytes:
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("Sheet1")
    date_style = xlwt.XFStyle()
    date_style.num_format_str = "DD/MM/YYYY"
    for row_index, row in enumerate(rows):
        for col_index, value in enumerate(row):
            if isinstance(value, date | datetime):
                sheet.write(row_index, col_index, value, date_style)
            else:
                sheet.write(row_index, col_index, value)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_reads_xlsx_header_and_rows() -> None:
    content = _build_xlsx(
        [
            ["data", "status_descricao", "empresa_nome"],
            [date(2026, 6, 1), "Aprovado", "RDN"],
            [date(2026, 6, 2), "Revisar Relatório", "RVD"],
        ]
    )
    rows = read_excel_rows(content, "xlsx")
    # openpyxl sempre devolve `datetime` para células com formato de data
    # (o Excel não tem um tipo "só data" nativo) — nunca `date` puro.
    assert rows == [
        {"data": datetime(2026, 6, 1), "status_descricao": "Aprovado", "empresa_nome": "RDN"},
        {"data": datetime(2026, 6, 2), "status_descricao": "Revisar Relatório", "empresa_nome": "RVD"},
    ]


def test_xlsx_skips_fully_blank_rows() -> None:
    content = _build_xlsx(
        [
            ["data", "status_descricao", "empresa_nome"],
            [date(2026, 6, 1), "Aprovado", "RDN"],
            [None, None, None],
        ]
    )
    rows = read_excel_rows(content, "xlsx")
    assert len(rows) == 1


def test_xlsx_missing_trailing_cells_become_none() -> None:
    content = _build_xlsx([["data", "status_descricao", "empresa_nome"], [date(2026, 6, 1), "Aprovado"]])
    rows = read_excel_rows(content, "xlsx")
    assert rows[0]["empresa_nome"] is None


def test_corrupted_xlsx_raises_file_format_error() -> None:
    with pytest.raises(FileFormatError):
        read_excel_rows(b"PK\x03\x04" + b"lixo binario invalido", "xlsx")


def test_reads_legacy_xls_with_date_cell() -> None:
    content = _build_xls(
        [
            ["data", "status_descricao", "empresa_nome"],
            [date(2026, 6, 1), "Aprovado", "RDN"],
        ]
    )
    rows = read_excel_rows(content, "xls")
    assert rows[0]["empresa_nome"] == "RDN"
    assert rows[0]["status_descricao"] == "Aprovado"
    assert isinstance(rows[0]["data"], date | datetime)


def test_corrupted_xls_raises_file_format_error() -> None:
    with pytest.raises(FileFormatError):
        read_excel_rows(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"lixo", "xls")
