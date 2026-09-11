"""Parser do RDO no servidor. Porta fielmente
`frontend/logic/features/rdo/importers/index.ts` (que por sua vez migrou
`handleRdoFiles()`/`combineAndRenderRdo()` do sistema original), trocando só
ONDE roda — a lógica de negócio (colunas obrigatórias, dedup entre arquivos,
conversão de linha) é idêntica.

Produz dicts no shape exato de `RdoRecordIn`
(`app/modules/rdo/schemas.py`) — `to_incremental_records()` do módulo RDO é
reaproveitado sem alteração nenhuma a partir daqui.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.modules.imports.parsers.base import FileParseResult
from app.modules.imports.parsers.csv_parser import read_csv_rows
from app.modules.imports.parsers.excel import read_excel_rows
from app.modules.imports.parsers.signatures import assert_valid_signature, extension_of
from app.modules.imports.registry import FileRowError
from app.shared.dates import parse_flex_date
from app.shared.normalization import normalize_rows, null_if_empty

__all__ = ["dedupe_rdo_rows", "parse_rdo_file", "to_rdo_record"]

REQUIRED_RDO_COLS = ("data", "status_descricao", "empresa_nome")


def parse_rdo_file(content: bytes, filename: str) -> FileParseResult:
    """Lê um arquivo (Excel ou CSV) e valida colunas obrigatórias. Nunca
    lança para erro de conteúdo — devolve em `errors`; só propaga
    `FileFormatError` (arquivo corrompido/assinatura inválida), que o
    chamador (service.py) converte num erro de arquivo inteiro."""
    extension = extension_of(filename)
    assert_valid_signature(content, extension)

    raw_rows = read_csv_rows(content) if extension == "csv" else read_excel_rows(content, extension)
    rows = normalize_rows(raw_rows)

    result = FileParseResult(file_name=filename, found=len(rows))
    if not rows:
        return result

    sample_keys = set(rows[0].keys())
    missing = [col for col in REQUIRED_RDO_COLS if col not in sample_keys]
    if missing:
        result.errors.append(
            FileRowError(row=None, field=None, message=f"Faltam colunas: {', '.join(missing)}.")
        )
        return result

    result.rows = rows
    return result


def dedupe_rdo_rows(all_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Remove linhas 100% idênticas ENTRE arquivos — `relatorio_id` sozinho
    repete legitimamente (várias linhas por grupo/disciplina do mesmo
    relatório), então só uma linha inteira idêntica conta como duplicata
    real. Porta `dedupeRdoRows` (TS) literalmente, inclusive a normalização
    de `datetime`/`date` para comparação por timestamp."""
    if not all_rows:
        return [], 0

    key_cols: set[str] = set()
    for row in all_rows:
        key_cols.update(row.keys())
    sorted_cols = sorted(key_cols)

    seen: set[str] = set()
    final_rows: list[dict[str, Any]] = []
    duplicates = 0
    for row in all_rows:
        parts: list[str] = []
        for col in sorted_cols:
            value = row.get(col)
            if isinstance(value, datetime):
                parts.append(str(value.timestamp() * 1000))
            elif isinstance(value, date):
                parts.append(str(datetime(value.year, value.month, value.day).timestamp() * 1000))
            else:
                parts.append(str(value))
        signature = "|".join(parts)
        if signature in seen:
            duplicates += 1
            continue
        seen.add(signature)
        final_rows.append(row)

    return final_rows, duplicates


def to_rdo_record(row: dict[str, Any]) -> dict[str, Any] | None:
    """Converte uma linha normalizada no dict que `RdoRecordIn` espera, ou
    `None` se faltar data/unidade — porta `toRdoRecord` (TS) literalmente."""
    data_referencia = parse_flex_date(row.get("data"))
    empresa_nome = null_if_empty(row.get("empresa_nome"))
    if data_referencia is None or empresa_nome is None:
        return None

    return {
        "dataReferencia": data_referencia.isoformat(),
        "empresaNome": empresa_nome,
        "statusDescricao": null_if_empty(row.get("status_descricao")) or "",
        "relatorioId": null_if_empty(row.get("relatorio_id")),
        "grupo": null_if_empty(row.get("grupo")),
        "disciplina": null_if_empty(row.get("disciplina")),
        "year": data_referencia.year,
        "month": data_referencia.month,
        "raw": {key: _json_safe(value) for key, value in row.items()},
    }


def _json_safe(value: Any) -> Any:
    """`raw` vai para uma coluna JSONB — datas precisam virar string."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value
