"""Testes de integração HTTP de `/justificativas`, contra Postgres real."""

from __future__ import annotations


async def test_viewer_forbidden_analyst_allowed(client, auth_header) -> None:
    forbidden = await client.get(
        "/api/v1/justificativas?module=rdo&year=2027", headers=auth_header("VIEWER")
    )
    assert forbidden.status_code == 403

    empty = await client.get(
        "/api/v1/justificativas?module=rdo&year=2027", headers=auth_header("ANALYST")
    )
    assert empty.status_code == 200
    assert empty.json()["records"] == []


async def test_save_then_list_then_delete_justification(client, auth_header) -> None:
    save = await client.put(
        "/api/v1/justificativas",
        json={
            "module": "rdo",
            "year": 2027,
            "month": 3,
            "text": "RDO abaixo da meta por atraso no fornecedor X.",
            "result": 70.0,
            "target": 80.0,
            "status": "BELOW_TARGET",
            "evidence": [{"label": "Resultado do mês", "value": "70%"}],
        },
        headers=auth_header("ANALYST"),
    )
    assert save.status_code == 200
    assert save.json()["record"]["text"].startswith("RDO abaixo")

    listed = await client.get(
        "/api/v1/justificativas?module=rdo&year=2027", headers=auth_header("ANALYST")
    )
    assert listed.status_code == 200
    assert len(listed.json()["records"]) == 1

    deleted = await client.delete(
        "/api/v1/justificativas?module=rdo&year=2027&month=3", headers=auth_header("ANALYST")
    )
    assert deleted.status_code == 200

    listed_after = await client.get(
        "/api/v1/justificativas?module=rdo&year=2027", headers=auth_header("ANALYST")
    )
    assert listed_after.json()["records"] == []


async def _import_records(client, auth_header, module: str, records: list[dict]) -> None:
    start = await client.post(
        "/api/v1/importacoes/iniciar",
        json={"module": module, "fileName": "dados.xlsx", "totalFound": len(records)},
        headers=auth_header("ANALYST"),
    )
    assert start.status_code == 200
    job_id = start.json()["importJobId"]
    batch = await client.post(
        f"/api/v1/importacoes/{job_id}/lotes",
        json={"batchNumber": 1, "records": records},
        headers=auth_header("ANALYST"),
    )
    assert batch.status_code == 200, batch.text
    finalize = await client.post(
        f"/api/v1/importacoes/{job_id}/finalizar", headers=auth_header("ANALYST")
    )
    assert finalize.status_code == 200


async def test_suggestion_endpoint_recalculates_from_real_records(client, auth_header) -> None:
    """`GET /justificativas/sugestao` recalcula o indicador a partir das
    tabelas de registros brutos — não recebe `result`/`evidence` prontos do
    chamador (ver decisions.md, correção aplicada após a reescrita para
    paridade real com o gerador RNC do TS original)."""
    await _import_records(
        client, auth_header, "rnc",
        [
            {
                "statusRnc": "TRATADA", "unidade": "UNIDADE A", "dataCriacao": "2027-03-05T00:00:00",
                "dataSolucao": "2027-03-20T00:00:00", "tempoTratativa": 20, "ofensor": "Fornecedor",
                "year": 2027, "month": 3, "raw": {},
            },
        ],
    )

    forbidden = await client.get(
        "/api/v1/justificativas/sugestao?module=rnc&year=2027&month=3&target=15",
        headers=auth_header("VIEWER"),
    )
    assert forbidden.status_code == 403

    response = await client.get(
        "/api/v1/justificativas/sugestao?module=rnc&year=2027&month=3&target=15",
        headers=auth_header("ANALYST"),
    )
    assert response.status_code == 200
    suggestion = response.json()["suggestion"]
    assert suggestion["status"] == "BELOW_TARGET"  # 20 dias > meta de 15
    assert suggestion["result"] == 20
    assert suggestion["suggestedText"]
    assert "UNIDADE A" in suggestion["suggestedText"]


async def test_suggestion_endpoint_no_data_returns_no_data_status(client, auth_header) -> None:
    response = await client.get(
        "/api/v1/justificativas/sugestao?module=rdo&year=2027&month=3&target=80",
        headers=auth_header("ANALYST"),
    )
    assert response.status_code == 200
    suggestion = response.json()["suggestion"]
    assert suggestion["status"] == "NO_DATA"
    assert suggestion["evidence"] == []


async def test_suggestion_endpoint_rdo(client, auth_header) -> None:
    await _import_records(
        client, auth_header, "rdo",
        [
            {
                "dataReferencia": "2027-03-05T00:00:00", "empresaNome": "UNIDADE A",
                "statusDescricao": "Revisar Relatório", "relatorioId": "R1", "grupo": "Mecânica",
                "disciplina": "Tubulação", "year": 2027, "month": 3, "raw": {},
            },
        ],
    )
    response = await client.get(
        "/api/v1/justificativas/sugestao?module=rdo&year=2027&month=3&target=80",
        headers=auth_header("ANALYST"),
    )
    assert response.status_code == 200
    suggestion = response.json()["suggestion"]
    assert suggestion["status"] == "BELOW_TARGET"
    assert suggestion["result"] == 0


async def test_suggestion_endpoint_idp(client, auth_header) -> None:
    await _import_records(
        client, auth_header, "idp",
        [
            {
                "unit": "Nova Mutum", "detectedUnit": "Nova Mutum", "unitAdjusted": False,
                "rsoNumero": 34, "detectedRsoNumero": 34, "rsoAdjusted": False,
                "referenceYear": 2027, "referenceMonth": 3, "detectedReferenceYear": 2027,
                "detectedReferenceMonth": 3, "referenceSource": "PDF_MES_REF",
                "referenceOriginalText": "Mês ref.: 03/2027", "referenceAdjusted": False,
                "periodStart": None, "periodEnd": None, "emissionDate": None,
                "fileName": "RSO 34.pdf", "areas": ["Pipe Rack"],
                "discData": {"01 - Civil": [{"area": "Pipe Rack", "prevAcum": 100, "realAcum": 50}]},
                "execucaoFases": [{"label": "Fase 1", "prevAcum": 53.08, "realAcum": 30.0}],
                "raw": {},
            },
        ],
    )
    response = await client.get(
        "/api/v1/justificativas/sugestao?module=idp&year=2027&month=3&target=90",
        headers=auth_header("ANALYST"),
    )
    assert response.status_code == 200
    suggestion = response.json()["suggestion"]
    assert suggestion["status"] == "BELOW_TARGET"
    assert suggestion["month"] == 3


async def test_suggestion_endpoint_cinco_s(client, auth_header) -> None:
    await _import_records(
        client, auth_header, "cinco-s",
        [
            {
                "unit": "LEM", "year": 2027, "month": 3,
                "areas": [{"divisao": "Manutenção", "area": "Almoxarifado", "meta": 0.9, "nota": 0.4}],
                "raw": {},
            },
        ],
    )
    response = await client.get(
        "/api/v1/justificativas/sugestao?module=cinco-s&year=2027&month=3&target=90",
        headers=auth_header("ANALYST"),
    )
    assert response.status_code == 200
    suggestion = response.json()["suggestion"]
    assert suggestion["status"] == "BELOW_TARGET"


async def test_suggestion_endpoint_taxa_acidentes(client, auth_header) -> None:
    monthly = await client.post(
        "/api/v1/taxa-acidentes",
        json={"type": "month", "year": 2027, "month": 3, "rate": 9.0, "caf": 2},
        headers=auth_header("ANALYST"),
    )
    assert monthly.status_code in (200, 201)

    response = await client.get(
        "/api/v1/justificativas/sugestao?module=taxa-acidentes&year=2027&month=3&target=7.5",
        headers=auth_header("ANALYST"),
    )
    assert response.status_code == 200
    suggestion = response.json()["suggestion"]
    assert suggestion["status"] == "BELOW_TARGET"
    assert suggestion["result"] == 9
    assert suggestion["sourceImport"] is None  # taxa de acidentes não tem motor de importação
