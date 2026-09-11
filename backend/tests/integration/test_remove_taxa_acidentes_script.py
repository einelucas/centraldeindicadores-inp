"""Testes de integração do script `scripts/remove_taxa_acidentes_data.py`,
contra Postgres real — cobre os requisitos #14 e #20 da migração
2026-alinhamento-v2 (dry-run não altera nada, apply remove só o escopo
exato e é idempotente)."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.database import SessionLocal  # noqa: E402
from app.models.audit import AuditLog  # noqa: E402
from app.models.imports import ImportJob  # noqa: E402
from app.models.indicators import IndicatorPublication, IndicatorResult  # noqa: E402
from app.models.records import ScorecardSnapshot  # noqa: E402
from app.models.settings import AppSetting  # noqa: E402
from scripts.remove_taxa_acidentes_data import (  # noqa: E402
    MODULE_KEY,
    SETTING_KEY,
    SNAPSHOT_VALUE_KEY,
    _scope,
    apply_data_cleanup,
)


async def _admin_user_id(client, auth_header) -> str:
    response = await client.get("/api/v1/auth/me", headers=auth_header("ADMIN"))
    return response.json()["id"]


async def _seed_residuals(db_session, admin_id: str) -> None:
    db_session.add(
        IndicatorPublication(
            module=MODULE_KEY, indicator="taxa", version=1, target=7.5, result=9.0, status="ACIMA",
            payload={"resultado": 9.0}, active=True, publishedById=admin_id,
        )
    )
    db_session.add(
        IndicatorResult(module=MODULE_KEY, indicator="taxa", year=2027, month=3, value=9.0, target=7.5)
    )
    db_session.add(AppSetting(key=SETTING_KEY, value=7.5))
    db_session.add(
        ImportJob(module=MODULE_KEY, fileName="fake.xlsx", totalFound=0, totalInserted=0, totalIgnored=0,
                   totalUpdated=0, totalRejected=0, userId=admin_id)
    )
    db_session.add(
        AuditLog(action="INDICATOR_SETTINGS_UPDATED", entity="AppSetting", entityId=SETTING_KEY,
                  metadata_={"module": MODULE_KEY})
    )
    db_session.add(
        ScorecardSnapshot(
            businessKey="SCORECARD:residual-test", contentHash="stale-hash", year=2027, month=3,
            raw={"values": {"rdo": 90.0, SNAPSHOT_VALUE_KEY: 3.0}},
            firstImportId="seed", lastImportId="seed",
        )
    )
    await db_session.commit()


async def test_dry_run_reports_scope_without_mutating(client, auth_header, db_session) -> None:
    admin_id = await _admin_user_id(client, auth_header)
    await _seed_residuals(db_session, admin_id)

    async with SessionLocal() as session:
        scope = await _scope(session)

    assert scope["indicator_publications"] == 1
    assert scope["indicator_results"] == 1
    assert scope["app_settings"] == 1
    assert scope["import_jobs"] == 1
    assert scope["audit_logs"] == 1
    assert scope["scorecard_snapshots_with_key"] == 1

    # Rodar de novo (o dry-run nunca escreve) deve reportar exatamente o mesmo escopo.
    async with SessionLocal() as session_again:
        scope_again = await _scope(session_again)
    assert scope_again == scope


async def test_apply_removes_only_the_exact_scope_and_is_idempotent(client, auth_header, db_session) -> None:
    admin_id = await _admin_user_id(client, auth_header)
    await _seed_residuals(db_session, admin_id)

    # Publicação de OUTRO módulo — não pode ser afetada pela limpeza.
    db_session.add(
        IndicatorPublication(
            module="rdo", indicator="aprovacao", version=1, target=80, result=90,
            payload={"resultado": 90, "emitidos": 10, "mensal": []}, active=True, publishedById=admin_id,
        )
    )
    await db_session.commit()

    async with SessionLocal() as session:
        await apply_data_cleanup(session)
        await session.commit()

    async with SessionLocal() as session:
        scope_after = await _scope(session)

    assert scope_after["indicator_publications"] == 0
    assert scope_after["indicator_results"] == 0
    assert scope_after["app_settings"] == 0
    assert scope_after["import_jobs"] == 0
    assert scope_after["audit_logs"] == 0
    assert scope_after["scorecard_snapshots_with_key"] == 0

    # O snapshot em si não foi apagado — só a chave `taxa_acidentes` — e o
    # valor de RDO (outro indicador) foi preservado.
    async with SessionLocal() as session:
        snapshot = (await session.execute(select(ScorecardSnapshot))).scalar_one()
        assert snapshot.raw["values"] == {"rdo": 90.0}
        assert snapshot.contentHash != "stale-hash"

    # A publicação de RDO (outro módulo) não foi afetada.
    async with SessionLocal() as session:
        result = await session.execute(
            select(IndicatorPublication).where(IndicatorPublication.module == "rdo")
        )
        assert result.scalar_one_or_none() is not None

    # Segunda rodada: idempotente, encontra 0 em tudo, sem erro.
    async with SessionLocal() as session:
        scope_second = await _scope(session)
    assert all(
        scope_second[key] in (0, False)
        for key in (
            "indicator_publications", "indicator_results", "app_settings", "import_jobs",
            "audit_logs", "scorecard_snapshots_with_key",
        )
    )
    async with SessionLocal() as session:
        await apply_data_cleanup(session)  # não deve levantar exceção
        await session.commit()
