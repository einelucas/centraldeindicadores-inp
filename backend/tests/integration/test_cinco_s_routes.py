"""Testes de integração HTTP do módulo 5S, contra Postgres real."""

from __future__ import annotations

import pytest


def _area(area: str, meta: float = 0.9, nota: float = 1.0) -> dict:
    return {"divisao": "Manutenção", "area": area, "meta": meta, "nota": nota}


def _row(unit: str, month: int = 3, notas: list[float] | None = None) -> dict:
    notas = notas if notas is not None else [1.0, 0.9]
    return {
        "unit": unit,
        "year": 2027,
        "month": month,
        "areas": [_area(f"Area{i}", nota=n) for i, n in enumerate(notas)],
        "raw": {},
    }


async def _import_records(client, auth_header, records: list[dict], batch_number: int = 1) -> str:
    start = await client.post(
        "/api/v1/importacoes/iniciar",
        json={"module": "cinco-s", "fileName": "planilha.xlsx", "totalFound": len(records)},
        headers=auth_header("ANALYST"),
    )
    assert start.status_code == 200
    job_id = start.json()["importJobId"]

    batch = await client.post(
        f"/api/v1/importacoes/{job_id}/lotes",
        json={"batchNumber": batch_number, "records": records},
        headers=auth_header("ANALYST"),
    )
    assert batch.status_code == 200, batch.text

    finalize = await client.post(f"/api/v1/importacoes/{job_id}/finalizar", headers=auth_header("ANALYST"))
    assert finalize.status_code == 200
    return job_id


async def test_import_then_get_cinco_s(client, auth_header) -> None:
    await _import_records(client, auth_header, [_row("LEM"), _row("MTU")])

    response = await client.get("/api/v1/cinco-s", headers=auth_header("VIEWER"))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["result"]["unitsCount"] == 2


async def test_patch_settings_recalculates(client, auth_header) -> None:
    await _import_records(client, auth_header, [_row("LEM", notas=[1.0, 1.0])])

    forbidden = await client.patch(
        "/api/v1/cinco-s", json={"target": 95, "excludedUnits": []}, headers=auth_header("VIEWER")
    )
    assert forbidden.status_code == 403

    ok = await client.patch(
        "/api/v1/cinco-s", json={"target": 95, "excludedUnits": ["lem"]}, headers=auth_header("ANALYST")
    )
    assert ok.status_code == 200
    assert ok.json()["excludedUnits"] == ["LEM"]

    after = await client.get("/api/v1/cinco-s", headers=auth_header("VIEWER"))
    # LEM agora está excluída -> nenhuma unidade elegível no último mês.
    assert after.json()["result"]["geral"] is None


async def test_delete_registros_requires_admin(client, auth_header) -> None:
    await _import_records(client, auth_header, [_row("LEM")])

    forbidden = await client.request(
        "DELETE", "/api/v1/cinco-s/registros", json={"all": True}, headers=auth_header("ANALYST")
    )
    assert forbidden.status_code == 403

    count = await client.get("/api/v1/cinco-s/registros", headers=auth_header("ADMIN"))
    assert count.json()["count"] == 1

    deleted = await client.request(
        "DELETE", "/api/v1/cinco-s/registros", json={"all": True}, headers=auth_header("ADMIN")
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 1


async def test_publish_and_read_back(client, auth_header) -> None:
    # `_area` usa meta=0.9 por padrão -> aderencia = min(nota/0.9, 1).
    # LEM: notas 1.0/1.0 -> clamp(1.11, 1)=1.0 cada -> unidade 1.0 (100%).
    # MTU: notas 0.5/0.5 -> 0.5/0.9=0.5556 cada -> unidade 0.5556 (55.56%).
    # Consolidado = média simples das 2 unidades = (1.0 + 0.5556) / 2 = 0.7778.
    await _import_records(client, auth_header, [_row("LEM", notas=[1.0, 1.0]), _row("MTU", notas=[0.5, 0.5])])

    published = await client.post(
        "/api/v1/publicacoes/cinco-s",
        json={"target": 90, "excludedUnits": []},
        headers=auth_header("ADMIN"),
    )
    assert published.status_code == 200
    assert published.json()["publication"]["version"] == 1
    assert published.json()["publication"]["payload"]["resultado"] == pytest.approx(77.777778, rel=1e-5)

    fetched = await client.get("/api/v1/publicacoes/cinco-s", headers=auth_header("VIEWER"))
    assert fetched.status_code == 200
    assert fetched.json()["publication"]["version"] == 1


async def test_publish_without_records_is_domain_error(client, auth_header) -> None:
    response = await client.post(
        "/api/v1/publicacoes/cinco-s", json={"target": 90}, headers=auth_header("ADMIN")
    )
    assert response.status_code == 422
