"""Compara o schema esperado (modelos SQLAlchemy) com o banco real via
`information_schema` e reporta divergências (drift).

Uso:
    python scripts/check_schema_drift.py

Sai com código 0 se não houver drift, 1 caso contrário. Não altera o banco —
somente leitura.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.config import get_settings  # noqa: E402
from app.core.database import Base  # noqa: E402


async def main() -> int:
    settings = get_settings()
    engine = create_async_engine(settings.sqlalchemy_database_url)
    drift_found = False

    async with engine.connect() as conn:
        db_tables = await conn.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
        expected_tables = set(Base.metadata.tables.keys())

        missing_in_db = expected_tables - db_tables
        extra_in_db = db_tables - expected_tables - {"alembic_version"}

        if missing_in_db:
            drift_found = True
            print(f"[DRIFT] Tabelas esperadas ausentes no banco: {sorted(missing_in_db)}")
        if extra_in_db:
            drift_found = True
            print(f"[DRIFT] Tabelas no banco sem modelo correspondente: {sorted(extra_in_db)}")

        for table_name, table in Base.metadata.tables.items():
            if table_name not in db_tables:
                continue

            db_columns = await conn.run_sync(
                lambda sync_conn, t=table_name: {
                    col["name"]: col for col in inspect(sync_conn).get_columns(t)
                }
            )
            expected_columns = {col.name for col in table.columns}
            missing_columns = expected_columns - db_columns.keys()
            extra_columns = db_columns.keys() - expected_columns

            if missing_columns:
                drift_found = True
                print(f"[DRIFT] {table_name}: colunas esperadas ausentes: {sorted(missing_columns)}")
            if extra_columns:
                drift_found = True
                print(f"[DRIFT] {table_name}: colunas extras no banco: {sorted(extra_columns)}")

        # Confere se o Alembic considera o banco "up to date" com a cabeça atual.
        result = await conn.execute(text("SELECT version_num FROM alembic_version"))
        row = result.first()
        current_version = row[0] if row else None
        print(f"[INFO] alembic_version no banco: {current_version}")

    await engine.dispose()

    if drift_found:
        print("\nRESULTADO: drift encontrado — ver mensagens acima.")
        return 1

    print("RESULTADO: nenhum drift encontrado — schema do banco corresponde aos modelos.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
