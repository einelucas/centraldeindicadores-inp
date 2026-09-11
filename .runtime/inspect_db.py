from __future__ import annotations

import os

import psycopg
from psycopg import sql

from app.core.config import get_settings


TABLES = (
    "RdoRecord",
    "IdpRecord",
    "IdpRsoRecord",
    "RncRecord",
    "FiveSRecord",
    "ScorecardSnapshot",
    "IndicatorResult",
    "IndicatorPublication",
    "ImportJob",
    "ImportFile",
)


settings = get_settings()
connection_url = os.getenv("INSPECT_DATABASE_URL", settings.alembic_database_url)
connection_url = connection_url.replace("postgresql+psycopg://", "postgresql://", 1)
with psycopg.connect(connection_url) as connection:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT table_schema, table_name "
            "FROM information_schema.tables "
            "WHERE table_schema NOT IN ('pg_catalog', 'information_schema') "
            "ORDER BY table_schema, table_name"
        )
        schema_tables = cursor.fetchall()
        public_tables = {table for schema, table in schema_tables if schema == "public"}

        print("COUNTS")
        for table in TABLES:
            if table not in public_tables:
                print(f"{table}: MISSING")
                continue
            cursor.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table)))
            print(f"{table}: {cursor.fetchone()[0]}")

        print("PUBLICATIONS")
        if "IndicatorPublication" in public_tables:
            cursor.execute(
                'SELECT module, indicator, active, count(*) '
                'FROM "IndicatorPublication" '
                'GROUP BY module, indicator, active '
                'ORDER BY module, indicator, active'
            )
            for row in cursor.fetchall():
                print(row)
            cursor.execute(
                'SELECT module, indicator, version, active, "publishedAt" '
                'FROM "IndicatorPublication" '
                "WHERE module IN ('rdo', 'idp', 'rnc', 'cinco-s') "
                'ORDER BY module, version'
            )
            for row in cursor.fetchall():
                print("META", row)
            cursor.execute(
                'SELECT module, indicator, version, payload '
                'FROM "IndicatorPublication" '
                "WHERE module IN ('rdo', 'idp', 'rnc', 'cinco-s') "
                'ORDER BY module, version'
            )
            for module, indicator, version, payload in cursor.fetchall():
                nested = {
                    key: sorted(value.keys())[:20]
                    for key, value in payload.items()
                    if isinstance(value, dict)
                }
                print("PAYLOAD", module, indicator, version, sorted(payload.keys()), nested)

        if "AppSetting" in public_tables:
            print("SETTINGS")
            cursor.execute('SELECT key, value FROM "AppSetting" ORDER BY key')
            for row in cursor.fetchall():
                print(row)

        print("SCHEMAS")
        for schema, table in schema_tables:
            cursor.execute(
                sql.SQL("SELECT count(*) FROM {}.{}").format(
                    sql.Identifier(schema), sql.Identifier(table)
                )
            )
            print(f"{schema}.{table}: {cursor.fetchone()[0]}")
