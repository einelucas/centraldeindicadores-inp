"""Testes do parser server-side de arquivos RNC."""

from __future__ import annotations

import io
from datetime import date

import openpyxl
import pytest

from app.modules.imports.parsers.base import FileFormatError
from app.modules.imports.parsers.rnc import dedupe_rnc_rows, parse_rnc_file, to_rnc_record


def _xlsx(rows: list[list[object]]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _headers() -> list[str]:
    return [
        "status_rnc",
        "unidade",
        "data_de_criação",
        "data_de_solução",
        "tempo_de_tratativa",
        "ofensor",
    ]


def test_parse_rnc_file_reads_accented_headers() -> None:
    result = parse_rnc_file(
        _xlsx([_headers(), ["TRATADA", "UNID A", date(2026, 1, 5), date(2026, 1, 12), 7, "Fornecedor"]]),
        "rnc.xlsx",
    )
    assert result.found == 1
    assert not result.errors
    assert result.rows[0]["data_de_criacao"].date() == date(2026, 1, 5)


def test_parse_rnc_file_detects_header_after_export_titles() -> None:
    result = parse_rnc_file(
        _xlsx(
            [
                ["Controle de Conformidade de Obra"],
                ["RNC"],
                ["Name", "Ação", "Disciplina", *_headers()],
                [
                    "RNC RVD 28", "RNC", "EIA", "TRATADA", "RVD",
                    date(2026, 7, 9), date(2026, 7, 22), 13, "Fornecedor",
                ],
                [
                    "RNC RVD 37", "RNC", "EIA", "PENDENTE", "RVD",
                    date(2026, 8, 21), "", "", "Exe. Obra",
                ],
            ]
        ),
        "controle-rnc.xlsx",
    )
    assert result.found == 2
    assert not result.errors
    assert result.rows[0]["status_rnc"] == "TRATADA"
    assert result.rows[1]["data_de_solucao"] in (None, "")


def test_parse_rnc_file_ignores_export_summary_row() -> None:
    result = parse_rnc_file(
        _xlsx(
            [
                ["Controle de Conformidade de Obra"],
                ["RNC"],
                [*_headers()],
                ["TRATADA", "RVD", date(2026, 7, 9), date(2026, 7, 22), 13, "Fornecedor"],
                ["", "", None, None, 14.8, ""],
            ]
        ),
        "controle-rnc.xlsx",
    )
    assert result.found == 1


def test_parse_rnc_file_reports_missing_columns() -> None:
    result = parse_rnc_file(_xlsx([["status_rnc", "unidade"], ["ABERTA", "UNID A"]]), "rnc.xlsx")
    assert not result.rows
    assert "data_de_criacao" in result.errors[0].message


def test_parse_rnc_file_rejects_corrupted_file() -> None:
    with pytest.raises(FileFormatError):
        parse_rnc_file("não é uma planilha".encode(), "rnc.xlsx")


def test_parse_rnc_file_handles_csv() -> None:
    content = (
        "status_rnc,unidade,data_de_criação,data_de_solução,tempo_de_tratativa,ofensor\n"
        "TRATADA,UNID A,05/01/2026,12/01/2026,7,Fornecedor\n"
    ).encode()
    result = parse_rnc_file(content, "rnc.csv")
    assert result.found == 1
    assert result.rows[0]["ofensor"] == "Fornecedor"


def test_dedupe_rnc_rows_only_removes_identical_rows() -> None:
    row = {"status_rnc": "TRATADA", "unidade": "A", "ofensor": "Fornecedor"}
    changed = {**row, "ofensor": "Processo"}
    rows, duplicates = dedupe_rnc_rows([row, dict(row), changed])
    assert rows == [row, changed]
    assert duplicates == 1


def test_to_rnc_record_converts_dates_and_br_number() -> None:
    record = to_rnc_record(
        {
            "status_rnc": " TRATADA ",
            "unidade": " unid a ",
            "data_de_criacao": "05/01/2026",
            "data_de_solucao": "12/01/2026",
            "tempo_de_tratativa": "1.234,5",
            "ofensor": " Fornecedor ",
        }
    )
    assert record is not None
    assert record["statusRnc"] == "TRATADA"
    assert record["dataCriacao"] == "2026-01-05T00:00:00"
    assert record["tempoTratativa"] == 1234.5
    assert record["year"] == 2026
    assert record["month"] == 1


def test_to_rnc_record_accepts_open_item_without_solution() -> None:
    record = to_rnc_record(
        {
            "status_rnc": "ABERTA",
            "unidade": "UNID A",
            "data_de_criacao": date(2026, 1, 5),
            "data_de_solucao": None,
            "tempo_de_tratativa": "NAN",
            "ofensor": "",
        }
    )
    assert record is not None
    assert record["dataSolucao"] is None
    assert record["tempoTratativa"] is None
    assert record["ofensor"] == "N/A"
    assert record["raw"]["data_de_criacao"] == "2026-01-05"


def test_to_rnc_record_rejects_row_without_creation_date() -> None:
    assert to_rnc_record({"data_de_criacao": None}) is None
