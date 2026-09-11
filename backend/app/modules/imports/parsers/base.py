"""Estruturas comuns produzidas por qualquer parser de arquivo (Excel/CSV/PDF).

Todo parser específico de módulo (`rdo.py`, `rnc.py`, ...) devolve um
`FileParseResult` — nunca lança para erros de conteúdo/formato de linha
(esses viram `ParseRowError`); só lança para erros verdadeiramente
excepcionais (arquivo corrompido, assinatura inválida), que o chamador
converte num `ParseRowError` de arquivo inteiro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.modules.imports.registry import FileRowError

__all__ = ["FileFormatError", "FileParseResult"]


@dataclass(slots=True)
class FileParseResult:
    """Resultado da leitura de UM arquivo, antes de qualquer dedup entre
    arquivos (isso é feito por quem chama o parser, agregando vários
    `FileParseResult`). `errors` reaproveita `FileRowError` do registry —
    mesmo formato usado na resposta consolidada do endpoint, sem duplicar a
    estrutura."""

    file_name: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    errors: list[FileRowError] = field(default_factory=list)
    found: int = 0
    """Total de linhas de dados encontradas no arquivo, mesmo as rejeitadas
    (equivalente ao `found` por arquivo da resposta consolidada)."""


class FileFormatError(Exception):
    """Arquivo corrompido, assinatura inválida, ou formato que não pôde ser
    interpretado de forma alguma (o arquivo inteiro é rejeitado, não uma
    linha)."""
