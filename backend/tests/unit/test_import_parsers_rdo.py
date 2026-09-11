"""Testes de `app/modules/imports/parsers/rdo.py` — colunas obrigatórias,
dedup entre arquivos e conversão de linha para o shape de `RdoRecordIn`.
Fiel a `frontend/logic/features/rdo/importers/index.ts` (a mesma lógica que
antes rodava no navegador)."""

from __future__ import annotations

import io
from datetime import date

import openpyxl
import pytest

from app.modules.imports.parsers.base import FileFormatError
from app.modules.imports.parsers.rdo import dedupe_rdo_rows, parse_rdo_file, to_rdo_record


def _xlsx(rows: list[list[object]]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_parse_rdo_file_reads_valid_xlsx() -> None:
    content = _xlsx(
        [
            ["data", "status_descricao", "empresa_nome"],
            [date(2026, 6, 1), "Aprovado", "RDN"],
        ]
    )
    result = parse_rdo_file(content, "planilha.xlsx")
    assert result.found == 1
    assert not result.errors
    assert len(result.rows) == 1


def test_parse_rdo_file_reports_missing_required_columns() -> None:
    content = _xlsx([["data", "empresa_nome"], [date(2026, 6, 1), "RDN"]])
    result = parse_rdo_file(content, "planilha.xlsx")
    assert not result.rows
    assert len(result.errors) == 1
    assert "status_descricao" in result.errors[0].message


def test_parse_rdo_file_rejects_corrupted_file() -> None:
    with pytest.raises(FileFormatError):
        parse_rdo_file(b"nao e uma planilha", "planilha.xlsx")


def test_parse_rdo_file_handles_csv() -> None:
    content = "data,status_descricao,empresa_nome\n01/06/2026,Aprovado,RDN\n".encode()
    result = parse_rdo_file(content, "planilha.csv")
    assert result.found == 1
    assert result.rows[0]["empresa_nome"] == "RDN"


def test_dedupe_removes_fully_identical_rows_across_files() -> None:
    row_a = {"data": "01/06/2026", "status_descricao": "Aprovado", "empresa_nome": "RDN"}
    row_b = dict(row_a)  # linha idêntica, simulando outro arquivo
    row_c = {"data": "02/06/2026", "status_descricao": "Aprovado", "empresa_nome": "RDN"}
    rows, duplicates = dedupe_rdo_rows([row_a, row_b, row_c])
    assert len(rows) == 2
    assert duplicates == 1


def test_dedupe_keeps_rows_that_only_share_relatorio_id() -> None:
    """`relatorio_id` sozinho repete legitimamente entre grupos/disciplinas —
    só uma linha 100% idêntica conta como duplicata."""
    row_a = {
        "data": "01/06/2026", "status_descricao": "Aprovado", "empresa_nome": "RDN",
        "relatorio_id": "123", "grupo": "A",
    }
    row_b = {**row_a, "grupo": "B"}
    rows, duplicates = dedupe_rdo_rows([row_a, row_b])
    assert len(rows) == 2
    assert duplicates == 0


def test_dedupe_empty_input() -> None:
    assert dedupe_rdo_rows([]) == ([], 0)


def test_to_rdo_record_converts_valid_row() -> None:
    row = {
        "data": "01/06/2026", "status_descricao": "Aprovado", "empresa_nome": "RDN",
        "relatorio_id": "1", "grupo": "A", "disciplina": "Civil",
    }
    record = to_rdo_record(row)
    assert record is not None
    assert record["dataReferencia"] == "2026-06-01T00:00:00"
    assert record["empresaNome"] == "RDN"
    assert record["statusDescricao"] == "Aprovado"
    assert record["year"] == 2026
    assert record["month"] == 6


def test_to_rdo_record_returns_none_without_date() -> None:
    row = {"data": None, "status_descricao": "Aprovado", "empresa_nome": "RDN"}
    assert to_rdo_record(row) is None


def test_to_rdo_record_returns_none_without_unit() -> None:
    row = {"data": "01/06/2026", "status_descricao": "Aprovado", "empresa_nome": None}
    assert to_rdo_record(row) is None


def test_to_rdo_record_defaults_empty_status_to_blank_string() -> None:
    row = {"data": "01/06/2026", "status_descricao": None, "empresa_nome": "RDN"}
    record = to_rdo_record(row)
    assert record is not None
    assert record["statusDescricao"] == ""


def test_to_rdo_record_serializes_dates_in_raw_for_jsonb() -> None:
    row = {"data": date(2026, 6, 1), "status_descricao": "Aprovado", "empresa_nome": "RDN"}
    record = to_rdo_record(row)
    assert record is not None
    assert record["raw"]["data"] == "2026-06-01"
