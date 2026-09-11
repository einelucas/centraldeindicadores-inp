"""Rotina controlada para remover os últimos resíduos do módulo Taxa de
Acidentes (descontinuado — ver docs/scorecard.md) das tabelas
compartilhadas, e aplicar a migration que remove suas duas tabelas
dedicadas (`AccidentMonthlyRecord`, `AccidentUnitRecord`).

NUNCA é chamado automaticamente por build/start/seed/CI. Uso manual:

    python scripts/remove_taxa_acidentes_data.py --dry-run   # não altera nada
    python scripts/remove_taxa_acidentes_data.py --apply     # remove de verdade

`--dry-run` (padrão se nenhuma flag for passada) só relata o que existe e o
que seria removido — não abre transação de escrita nenhuma. `--apply` exige
a flag explicitamente, roda tudo em uma única transação, usa somente nomes
fixos e filtros exatos (nunca `LIKE`/curinga), e ao final aplica a migration
`7c7156aae822_remove_taxa_acidentes` via `alembic upgrade head`. As duas
operações são idempotentes: rodar de novo depois de um `--apply` bem
sucedido encontra 0 linhas e uma migration já aplicada, sem erro.
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import delete, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.audit import AuditLog  # noqa: E402
from app.models.imports import ImportJob  # noqa: E402
from app.models.indicators import IndicatorJustification, IndicatorPublication, IndicatorResult  # noqa: E402
from app.models.records import ScorecardSnapshot  # noqa: E402
from app.models.settings import AppSetting  # noqa: E402
from app.shared.hashing import make_content_hash  # noqa: E402

MODULE_KEY = "taxa-acidentes"
SNAPSHOT_VALUE_KEY = "taxa_acidentes"
SETTING_KEY = "taxa-acidentes.target"
ACCIDENT_ENTITIES = ("AccidentMonthlyRecord", "AccidentUnitRecord")
ACCIDENT_TABLES = ("AccidentMonthlyRecord", "AccidentUnitRecord")

_PRODUCTION_HINTS = ("prod", "production", "prd")


def _describe_url_without_secret(url: str) -> str:
    parts = urlsplit(url)
    host = parts.hostname or "?"
    port = parts.port or "?"
    user = parts.username or "?"
    database = parts.path.lstrip("/") or "?"
    return f"host={host} port={port} user={user} database={database}"


def _guard_target() -> None:
    settings = get_settings()
    lowered = settings.database_url.lower()
    if any(hint in lowered for hint in _PRODUCTION_HINTS):
        raise SystemExit(
            "Bloqueado: a URL de conexão contém indício de produção "
            f"({_describe_url_without_secret(settings.database_url)}). Este script "
            "nunca deve rodar contra produção."
        )
    print(f"[remove-taxa-acidentes] Alvo confirmado (sem senha): "
          f"{_describe_url_without_secret(settings.database_url)}")
    print(f"[remove-taxa-acidentes] APP_ENV={settings.app_env}")


async def _table_exists(session: AsyncSession, table_name: str) -> bool:
    result = await session.execute(text("SELECT to_regclass(:name) IS NOT NULL"), {"name": f'"{table_name}"'})
    return bool(result.scalar())


async def _accident_table_row_count(session: AsyncSession, table_name: str) -> int:
    if not await _table_exists(session, table_name):
        return 0
    result = await session.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))  # nosec: nome fixo, não interpolado de input externo
    return int(result.scalar() or 0)


async def _snapshots_with_taxa_acidentes_key(session: AsyncSession) -> list[ScorecardSnapshot]:
    result = await session.execute(select(ScorecardSnapshot))
    return [
        snapshot
        for snapshot in result.scalars().all()
        if isinstance(snapshot.raw, dict)
        and isinstance(snapshot.raw.get("values"), dict)
        and SNAPSHOT_VALUE_KEY in snapshot.raw["values"]
    ]


async def _scope(session: AsyncSession) -> dict[str, int | bool]:
    accident_monthly_exists = await _table_exists(session, "AccidentMonthlyRecord")
    accident_unit_exists = await _table_exists(session, "AccidentUnitRecord")

    publications = await session.scalar(
        select(text("COUNT(*)"))
        .select_from(IndicatorPublication)
        .where(IndicatorPublication.module == MODULE_KEY)
    )
    results = await session.scalar(
        select(text("COUNT(*)")).select_from(IndicatorResult).where(IndicatorResult.module == MODULE_KEY)
    )
    justifications = await session.scalar(
        select(text("COUNT(*)")).select_from(IndicatorJustification).where(
            IndicatorJustification.module == MODULE_KEY
        )
    )
    import_jobs = await session.scalar(
        select(text("COUNT(*)")).select_from(ImportJob).where(ImportJob.module == MODULE_KEY)
    )
    settings_rows = await session.scalar(
        select(text("COUNT(*)")).select_from(AppSetting).where(AppSetting.key == SETTING_KEY)
    )
    audit_rows = await session.scalar(
        select(text("COUNT(*)")).select_from(AuditLog).where(
            (AuditLog.metadata_["module"].astext == MODULE_KEY)
            | AuditLog.entity.in_(ACCIDENT_ENTITIES)
            | (AuditLog.entityId == SETTING_KEY)
        )
    )
    snapshots = await _snapshots_with_taxa_acidentes_key(session)

    return {
        "accident_monthly_table_exists": accident_monthly_exists,
        "accident_unit_table_exists": accident_unit_exists,
        "accident_monthly_rows": await _accident_table_row_count(session, "AccidentMonthlyRecord"),
        "accident_unit_rows": await _accident_table_row_count(session, "AccidentUnitRecord"),
        "indicator_publications": publications or 0,
        "indicator_results": results or 0,
        "indicator_justifications": justifications or 0,
        "import_jobs": import_jobs or 0,
        "app_settings": settings_rows or 0,
        "audit_logs": audit_rows or 0,
        "scorecard_snapshots_with_key": len(snapshots),
    }


def _print_scope(scope: dict[str, int | bool], *, verb: str) -> None:
    p = "[remove-taxa-acidentes]"
    print(f"{p} Tabela AccidentMonthlyRecord existe: {scope['accident_monthly_table_exists']}")
    print(f"{p} Tabela AccidentUnitRecord existe: {scope['accident_unit_table_exists']}")
    print(f"{p} AccidentMonthlyRecord — linhas a {verb}: {scope['accident_monthly_rows']}")
    print(f"{p} AccidentUnitRecord — linhas a {verb}: {scope['accident_unit_rows']}")
    print(f"{p} IndicatorPublication (module='{MODULE_KEY}') a {verb}: {scope['indicator_publications']}")
    print(f"{p} IndicatorResult (module='{MODULE_KEY}') a {verb}: {scope['indicator_results']}")
    print(f"{p} IndicatorJustification (module='{MODULE_KEY}') a {verb}: "
          f"{scope['indicator_justifications']}")
    print(f"{p} ImportJob (module='{MODULE_KEY}') a {verb}: {scope['import_jobs']} "
          "(esperado 0 — módulo nunca usou o motor de importação)")
    print(f"{p} AppSetting (key='{SETTING_KEY}') a {verb}: {scope['app_settings']}")
    print(f"{p} AuditLog relacionado a {verb}: {scope['audit_logs']}")
    print(f"{p} ScorecardSnapshot com a chave '{SNAPSHOT_VALUE_KEY}' a limpar: "
          f"{scope['scorecard_snapshots_with_key']}")


async def _run_dry_run() -> None:
    _guard_target()
    async with SessionLocal() as session:
        scope = await _scope(session)
    _print_scope(scope, verb="remover")
    print("[remove-taxa-acidentes] DRY-RUN concluído — nenhum dado foi alterado.")


async def apply_data_cleanup(session: AsyncSession) -> None:
    """A parte pura de limpeza de dados do `--apply` — sem `commit()` (fica a
    cargo do chamador) e sem chamar o Alembic. Extraída à parte para poder
    ser exercitada diretamente por testes de integração."""
    for table_name in ACCIDENT_TABLES:
        if await _table_exists(session, table_name):
            await session.execute(text(f'DELETE FROM "{table_name}"'))

    await session.execute(delete(IndicatorPublication).where(IndicatorPublication.module == MODULE_KEY))
    await session.execute(delete(IndicatorResult).where(IndicatorResult.module == MODULE_KEY))
    await session.execute(delete(IndicatorJustification).where(IndicatorJustification.module == MODULE_KEY))
    # `ImportBatch`/`ImportError` têm FK para `ImportJob.id` com
    # `ondelete="CASCADE"` — apagar o job basta, o banco cuida do resto.
    await session.execute(delete(ImportJob).where(ImportJob.module == MODULE_KEY))
    await session.execute(delete(AppSetting).where(AppSetting.key == SETTING_KEY))
    await session.execute(
        delete(AuditLog).where(
            (AuditLog.metadata_["module"].astext == MODULE_KEY)
            | AuditLog.entity.in_(ACCIDENT_ENTITIES)
            | (AuditLog.entityId == SETTING_KEY)
        )
    )

    snapshots = await _snapshots_with_taxa_acidentes_key(session)
    for snapshot in snapshots:
        values = dict(snapshot.raw["values"])
        del values[SNAPSHOT_VALUE_KEY]
        new_raw = {**snapshot.raw, "values": values}
        new_hash = make_content_hash({k: v if v is not None else "" for k, v in sorted(values.items())})
        snapshot.raw = new_raw
        snapshot.contentHash = new_hash


async def _run_apply() -> None:
    _guard_target()
    async with SessionLocal() as session:
        scope_before = await _scope(session)
        try:
            await apply_data_cleanup(session)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise SystemExit(
                "[remove-taxa-acidentes] Falhou no meio da limpeza — nada foi commitado (rollback)."
            ) from exc

    async with SessionLocal() as verify_session:
        scope_after = await _scope(verify_session)

    _print_scope(scope_before, verb="removido")
    print("[remove-taxa-acidentes] Limpeza de dados concluída. Aplicando migration (alembic upgrade head)...")

    result = await asyncio.to_thread(
        subprocess.run,  # noqa: S603
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND_ROOT),
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            "[remove-taxa-acidentes] Falhou ao aplicar a migration — dados já foram limpos, "
            "mas as tabelas AccidentMonthlyRecord/AccidentUnitRecord podem ainda existir. "
            "Rode `alembic upgrade head` manualmente e investigue."
        )

    remaining = (
        scope_after["accident_monthly_rows"]
        + scope_after["accident_unit_rows"]
        + scope_after["indicator_publications"]
        + scope_after["indicator_results"]
        + scope_after["indicator_justifications"]
        + scope_after["import_jobs"]
        + scope_after["app_settings"]
        + scope_after["audit_logs"]
        + scope_after["scorecard_snapshots_with_key"]
    )
    if remaining:
        raise SystemExit(
            f"[remove-taxa-acidentes] Limpeza aplicada, mas ainda restam {remaining} linha(s) "
            "correspondentes ao escopo — investigue antes de considerar concluído."
        )
    print("[remove-taxa-acidentes] APPLY concluído: dados limpos e migration aplicada. Segunda execução "
          "encontrará 0 linhas (idempotente).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Só relata o escopo, não altera nada (padrão).")
    mode.add_argument("--apply", action="store_true", help="Remove de verdade — exige esta flag.")
    args = parser.parse_args()

    if args.apply:
        asyncio.run(_run_apply())
    else:
        asyncio.run(_run_dry_run())


if __name__ == "__main__":
    main()
