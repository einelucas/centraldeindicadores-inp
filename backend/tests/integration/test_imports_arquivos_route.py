"""Testes de `POST /api/v1/importacoes/{modulo}/arquivos` — upload
multipart, parsing/validação/normalização/dedup/persistência inteiramente
no servidor. RDO é o único módulo com `file_import` implementado nesta fase."""

from __future__ import annotations

import io

import openpyxl
import pytest
from sqlalchemy import select

from app.models.records import RdoRecord

_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx_bytes(rows: list[list[object]]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _rdo_rows(entries: list[tuple[str, str, str]]) -> list[list[object]]:
    """`entries`: (data DD/MM/YYYY, status, unidade)."""
    header = ["data", "status_descricao", "empresa_nome"]
    return [header, *[[e[0], e[1], e[2]] for e in entries]]


async def test_upload_single_xlsx_inserts_records(client, auth_header) -> None:
    content = _xlsx_bytes(_rdo_rows([("01/06/2026", "Aprovado", "RDN"), ("02/06/2026", "Aprovado", "RVD")]))
    response = await client.post(
        "/api/v1/importacoes/rdo/arquivos",
        files=[("files", ("planilha.xlsx", content, _XLSX_CONTENT_TYPE))],
        headers=auth_header("ADMIN"),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["totals"] == {"found": 2, "inserted": 2, "ignored": 0, "updated": 0, "rejected": 0}
    assert len(body["files"]) == 1
    assert body["files"][0]["fileName"] == "planilha.xlsx"
    assert body["files"][0]["accepted"] == 2
    assert "durationMs" in body


async def test_upload_multiple_files_same_request(client, auth_header) -> None:
    file_a = _xlsx_bytes(_rdo_rows([("01/06/2026", "Aprovado", "RDN")]))
    file_b_csv = b"data,status_descricao,empresa_nome\n02/06/2026,Aprovado,RVD\n"
    response = await client.post(
        "/api/v1/importacoes/rdo/arquivos",
        files=[
            ("files", ("a.xlsx", file_a, _XLSX_CONTENT_TYPE)),
            ("files", ("b.csv", file_b_csv, "text/csv")),
        ],
        headers=auth_header("ADMIN"),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["totals"]["inserted"] == 2
    assert len(body["files"]) == 2
    assert {f["fileName"] for f in body["files"]} == {"a.xlsx", "b.csv"}


async def test_dedupes_identical_rows_across_files(client, auth_header) -> None:
    rows = _rdo_rows([("01/06/2026", "Aprovado", "RDN")])
    content = _xlsx_bytes(rows)
    response = await client.post(
        "/api/v1/importacoes/rdo/arquivos",
        files=[
            ("files", ("a.xlsx", content, _XLSX_CONTENT_TYPE)),
            ("files", ("b.xlsx", content, _XLSX_CONTENT_TYPE)),
        ],
        headers=auth_header("ADMIN"),
    )
    body = response.json()
    assert body["totals"]["inserted"] == 1


async def test_reimport_updates_changed_record(client, auth_header, db_session) -> None:
    first = _xlsx_bytes(_rdo_rows([("01/06/2026", "Preenchendo Relatório", "RDN")]))
    await client.post(
        "/api/v1/importacoes/rdo/arquivos",
        files=[("files", ("a.xlsx", first, _XLSX_CONTENT_TYPE))],
        headers=auth_header("ADMIN"),
    )
    second = _xlsx_bytes(_rdo_rows([("01/06/2026", "Aprovado", "RDN")]))
    response = await client.post(
        "/api/v1/importacoes/rdo/arquivos",
        files=[("files", ("a.xlsx", second, _XLSX_CONTENT_TYPE))],
        headers=auth_header("ADMIN"),
    )
    body = response.json()
    assert body["totals"] == {"found": 1, "inserted": 0, "ignored": 0, "updated": 1, "rejected": 0}

    row = (await db_session.execute(select(RdoRecord))).scalar_one()
    assert row.statusDescricao == "Aprovado"


async def test_reimport_identical_file_is_ignored(client, auth_header) -> None:
    content = _xlsx_bytes(_rdo_rows([("01/06/2026", "Aprovado", "RDN")]))
    await client.post(
        "/api/v1/importacoes/rdo/arquivos",
        files=[("files", ("a.xlsx", content, _XLSX_CONTENT_TYPE))],
        headers=auth_header("ADMIN"),
    )
    response = await client.post(
        "/api/v1/importacoes/rdo/arquivos",
        files=[("files", ("a.xlsx", content, _XLSX_CONTENT_TYPE))],
        headers=auth_header("ADMIN"),
    )
    body = response.json()
    assert body["totals"]["ignored"] == 1
    assert body["totals"]["inserted"] == 0


async def test_missing_required_column_is_rejected_with_clear_message(client, auth_header) -> None:
    content = _xlsx_bytes([["data", "empresa_nome"], ["01/06/2026", "RDN"]])
    response = await client.post(
        "/api/v1/importacoes/rdo/arquivos",
        files=[("files", ("a.xlsx", content, _XLSX_CONTENT_TYPE))],
        headers=auth_header("ADMIN"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["files"][0]["accepted"] == 0
    assert "status_descricao" in body["files"][0]["errors"][0]["message"]


async def test_empty_file_produces_no_records_no_error(client, auth_header) -> None:
    content = _xlsx_bytes([["data", "status_descricao", "empresa_nome"]])
    response = await client.post(
        "/api/v1/importacoes/rdo/arquivos",
        files=[("files", ("vazio.xlsx", content, _XLSX_CONTENT_TYPE))],
        headers=auth_header("ADMIN"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["files"][0]["found"] == 0
    assert body["totals"]["inserted"] == 0


async def test_corrupted_file_is_rejected_as_domain_error(client, auth_header) -> None:
    response = await client.post(
        "/api/v1/importacoes/rdo/arquivos",
        files=[("files", ("a.xlsx", b"nao e uma planilha valida", _XLSX_CONTENT_TYPE))],
        headers=auth_header("ADMIN"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["files"][0]["rejected"] >= 0
    assert body["files"][0]["errors"]


async def test_unsupported_extension_returns_domain_error(client, auth_header) -> None:
    response = await client.post(
        "/api/v1/importacoes/rdo/arquivos",
        files=[("files", ("a.docx", b"conteudo", "application/octet-stream"))],
        headers=auth_header("ADMIN"),
    )
    assert response.status_code == 422


async def test_no_files_returns_domain_error(client, auth_header) -> None:
    response = await client.post(
        "/api/v1/importacoes/rdo/arquivos",
        files=[],
        headers=auth_header("ADMIN"),
    )
    assert response.status_code in (400, 422)


async def test_idempotency_key_returns_same_result_without_reprocessing(client, auth_header) -> None:
    content = _xlsx_bytes(_rdo_rows([("01/06/2026", "Aprovado", "RDN")]))
    headers = {**auth_header("ADMIN"), "Idempotency-Key": "chave-fixa-123"}
    first = await client.post(
        "/api/v1/importacoes/rdo/arquivos",
        files=[("files", ("a.xlsx", content, _XLSX_CONTENT_TYPE))],
        headers=headers,
    )
    second = await client.post(
        "/api/v1/importacoes/rdo/arquivos",
        files=[("files", ("a.xlsx", content, _XLSX_CONTENT_TYPE))],
        headers=headers,
    )
    assert first.json()["importJobId"] == second.json()["importJobId"]
    assert second.json()["totals"]["inserted"] == 1  # não reprocessado -> mesmo total do primeiro envio


async def test_viewer_cannot_import_files(client, auth_header) -> None:
    content = _xlsx_bytes(_rdo_rows([("01/06/2026", "Aprovado", "RDN")]))
    response = await client.post(
        "/api/v1/importacoes/rdo/arquivos",
        files=[("files", ("a.xlsx", content, _XLSX_CONTENT_TYPE))],
        headers=auth_header("VIEWER"),
    )
    assert response.status_code == 403


@pytest.mark.parametrize("modulo", ["rnc", "cinco-s", "idp"])
async def test_modules_not_yet_migrated_return_501(client, auth_header, modulo: str) -> None:
    response = await client.post(
        f"/api/v1/importacoes/{modulo}/arquivos",
        files=[("files", ("a.xlsx", b"qualquer coisa", _XLSX_CONTENT_TYPE))],
        headers=auth_header("ADMIN"),
    )
    assert response.status_code == 501
