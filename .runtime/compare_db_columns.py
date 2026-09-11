from __future__ import annotations

from pathlib import Path

import psycopg


SOURCE_ENV = Path(r"C:\Users\lucas.pinheiro\Documents\central-nuxt\backend\.env")
TARGET_ENV = Path(r"C:\Users\lucas.pinheiro\Documents\centraldeindicadores_nuxt\backend\.env")
TABLES = ("User", "AppSetting", "IndicatorResult", "IndicatorPublication", "ScorecardSnapshot")


def read_database_url(path: Path) -> str:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if raw_line.startswith("DATABASE_URL="):
            value = raw_line.partition("=")[2].strip().strip('"').strip("'")
            return value.replace("postgresql+psycopg://", "postgresql://", 1)
    raise RuntimeError(f"DATABASE_URL ausente em {path}")


def columns(connection: psycopg.Connection, table: str) -> list[tuple[str, str, str]]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s "
            "ORDER BY ordinal_position",
            (table,),
        )
        return list(cursor.fetchall())


with psycopg.connect(read_database_url(SOURCE_ENV)) as source:
    with psycopg.connect(read_database_url(TARGET_ENV)) as target:
        for table in TABLES:
            print(f"TABLE {table}")
            print("SOURCE", columns(source, table))
            print("TARGET", columns(target, table))
