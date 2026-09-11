"""Testes de `app/modules/imports/parsers/csv_parser.py` — detecção de
codificação (UTF-8/UTF-8 BOM/cp1252/latin-1) e de delimitador (`,`/`;`/tab)."""

from __future__ import annotations

from app.modules.imports.parsers.csv_parser import read_csv_rows


def test_reads_comma_delimited_utf8() -> None:
    content = b"data,status_descricao,empresa_nome\n01/06/2026,Aprovado,RDN\n"
    rows = read_csv_rows(content)
    assert rows == [{"data": "01/06/2026", "status_descricao": "Aprovado", "empresa_nome": "RDN"}]


def test_reads_semicolon_delimited() -> None:
    content = b"data;status_descricao;empresa_nome\n01/06/2026;Aprovado;RDN\n"
    rows = read_csv_rows(content)
    assert rows == [{"data": "01/06/2026", "status_descricao": "Aprovado", "empresa_nome": "RDN"}]


def test_reads_tab_delimited() -> None:
    content = b"data\tstatus_descricao\tempresa_nome\n01/06/2026\tAprovado\tRDN\n"
    rows = read_csv_rows(content)
    assert rows == [{"data": "01/06/2026", "status_descricao": "Aprovado", "empresa_nome": "RDN"}]


def test_reads_utf8_bom() -> None:
    text = "data,status_descricao,empresa_nome\n01/06/2026,Aprovado,RDN\n"
    content = text.encode("utf-8-sig")
    assert content.startswith(b"\xef\xbb\xbf")  # confirma que o BOM está no início dos bytes
    rows = read_csv_rows(content)
    assert rows == [{"data": "01/06/2026", "status_descricao": "Aprovado", "empresa_nome": "RDN"}]


def test_reads_cp1252_with_accented_characters() -> None:
    content = "data,status_descricao,empresa_nome\n01/06/2026,Revisar Relatório,RONDONÓPOLIS\n".encode(
        "cp1252"
    )
    rows = read_csv_rows(content)
    assert rows[0]["status_descricao"] == "Revisar Relatório"
    assert rows[0]["empresa_nome"] == "RONDONÓPOLIS"


def test_empty_file_returns_no_rows() -> None:
    assert read_csv_rows(b"") == []
    assert read_csv_rows(b"   \n  ") == []


def test_blank_rows_are_skipped() -> None:
    content = b"data,status_descricao,empresa_nome\n01/06/2026,Aprovado,RDN\n,,\n"
    rows = read_csv_rows(content)
    assert len(rows) == 1
