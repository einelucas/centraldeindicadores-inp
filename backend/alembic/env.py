"""Alembic env.py com salvaguardas obrigatórias de segurança do banco.

Regras (ver docs/backend-migration-decisions.md e backend/README.md):
- migrations só rodam quando APP_ENV in {"test", "development"} E
  ALLOW_TEST_DB_MIGRATIONS=true;
- o host/porta/usuário/banco (nunca a senha) são impressos antes de qualquer
  operação, para conferência manual;
- qualquer indício de apontar para produção interrompe a migration.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path
from urllib.parse import urlsplit

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.database import Base  # noqa: E402
import app.models  # noqa: E402,F401  — garante que todos os modelos sejam registrados

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_PRODUCTION_HINTS = ("prod", "production", "prd")


def _describe_url_without_secret(url: str) -> str:
    parts = urlsplit(url)
    host = parts.hostname or "?"
    port = parts.port or "?"
    user = parts.username or "?"
    database = parts.path.lstrip("/") or "?"
    return f"host={host} port={port} user={user} database={database}"


def _guard_migration_target() -> str:
    settings = get_settings()

    if settings.app_env not in ("test", "development"):
        raise SystemExit(
            f"Migrations bloqueadas: APP_ENV='{settings.app_env}' não é 'test' "
            "nem 'development'. Nunca execute Alembic contra produção por este "
            "caminho."
        )

    if not settings.allow_test_db_migrations:
        raise SystemExit(
            "Migrations bloqueadas: defina ALLOW_TEST_DB_MIGRATIONS=true "
            "explicitamente para confirmar que o banco alvo é de teste/dev."
        )

    url = settings.alembic_database_url
    description = _describe_url_without_secret(settings.migration_database_url or settings.database_url)

    lowered = url.lower()
    if any(hint in lowered for hint in _PRODUCTION_HINTS):
        raise SystemExit(
            "Migrations bloqueadas: a URL de conexão contém um indício de "
            f"produção ({description}). Interrompendo por segurança."
        )

    print(f"[alembic] Alvo confirmado (sem senha): {description}")
    print(f"[alembic] APP_ENV={settings.app_env} ALLOW_TEST_DB_MIGRATIONS={settings.allow_test_db_migrations}")

    return url


def run_migrations_offline() -> None:
    url = _guard_migration_target()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _guard_migration_target()
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = url
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
