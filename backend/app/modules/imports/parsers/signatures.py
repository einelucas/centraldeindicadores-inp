"""Validação da assinatura real do arquivo (magic bytes) — nunca confia só
na extensão do nome. Formatos aceitos pela importação:

- ZIP/OPC (xlsx, xlsm, xltx, xlsb): assinatura `PK\\x03\\x04` (ou `PK\\x05\\x06`
  para um zip vazio, e `PK\\x07\\x08` para um "spanned archive" — raro, mas
  ambos ainda são ZIP válidos).
- OLE2/BIFF (xls, xlt legado): assinatura `D0 CF 11 E0 A1 B1 1A E1`.
- PDF: assinatura `%PDF-`.
- CSV: sem assinatura binária própria — validado por conteúdo (decodifica
  como texto numa das codificações aceitas).
"""

from __future__ import annotations

from app.modules.imports.parsers.base import FileFormatError

_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
_OLE2_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_PDF_SIGNATURE = b"%PDF-"

_ZIP_EXTENSIONS = {"xlsx", "xlsm", "xltx", "xlsb"}
_OLE2_EXTENSIONS = {"xls", "xlt"}


def extension_of(filename: str) -> str:
    """Extensão em minúsculas, sem o ponto. `""` se não houver."""
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def assert_valid_signature(content: bytes, extension: str) -> None:
    """Levanta `FileFormatError` se os bytes não batem com a assinatura
    esperada para a extensão declarada — cobre arquivos corrompidos e
    extensões trocadas de propósito."""
    if extension in _ZIP_EXTENSIONS:
        if not content.startswith(_ZIP_SIGNATURES):
            raise FileFormatError(
                f"O arquivo declara extensão .{extension}, mas não é um pacote Excel válido."
            )
        return
    if extension in _OLE2_EXTENSIONS:
        if not content.startswith(_OLE2_SIGNATURE):
            raise FileFormatError(
                f"O arquivo declara extensão .{extension}, mas não é um arquivo Excel legado válido."
            )
        return
    if extension == "pdf":
        if not content.startswith(_PDF_SIGNATURE):
            raise FileFormatError("O arquivo declara extensão .pdf, mas não é um PDF válido.")
        return
    if extension == "csv":
        # CSV é texto puro — a validação real acontece ao tentar decodificar
        # (ver parsers/csv_parser.py); aqui só rejeitamos um CSV que na
        # verdade é um Excel/PDF disfarçado com extensão trocada.
        if content.startswith(_ZIP_SIGNATURES) or content.startswith(_OLE2_SIGNATURE) or content.startswith(
            _PDF_SIGNATURE
        ):
            raise FileFormatError("O arquivo declara extensão .csv, mas o conteúdo é binário.")
        return
    raise FileFormatError(f"Extensão .{extension or '(nenhuma)'} não é aceita para importação.")
