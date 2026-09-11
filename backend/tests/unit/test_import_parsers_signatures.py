"""Testes de `app/modules/imports/parsers/signatures.py`."""

from __future__ import annotations

import pytest

from app.modules.imports.parsers.base import FileFormatError
from app.modules.imports.parsers.signatures import assert_valid_signature, extension_of


def test_extension_of_lowercases_and_strips_dot() -> None:
    assert extension_of("Planilha.XLSX") == "xlsx"
    assert extension_of("arquivo.csv") == "csv"
    assert extension_of("sem_extensao") == ""


def test_valid_zip_signature_accepted_for_xlsx() -> None:
    assert_valid_signature(b"PK\x03\x04" + b"resto", "xlsx")


def test_valid_ole2_signature_accepted_for_xls() -> None:
    assert_valid_signature(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"resto", "xls")


def test_valid_pdf_signature_accepted() -> None:
    assert_valid_signature(b"%PDF-1.7\n", "pdf")


def test_valid_csv_plain_text_accepted() -> None:
    assert_valid_signature(b"data,status\n1,2", "csv")


def test_xlsx_with_wrong_bytes_is_rejected() -> None:
    with pytest.raises(FileFormatError):
        assert_valid_signature(b"nao e um zip", "xlsx")


def test_xls_with_wrong_bytes_is_rejected() -> None:
    with pytest.raises(FileFormatError):
        assert_valid_signature(b"PK\x03\x04", "xls")


def test_csv_disguising_a_zip_is_rejected() -> None:
    with pytest.raises(FileFormatError):
        assert_valid_signature(b"PK\x03\x04" + b"na verdade um xlsx", "csv")


def test_unknown_extension_is_rejected() -> None:
    with pytest.raises(FileFormatError):
        assert_valid_signature(b"qualquer coisa", "docx")
