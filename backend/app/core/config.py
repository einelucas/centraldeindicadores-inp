"""Configuração da aplicação via variáveis de ambiente (Pydantic Settings).

Espelha as variáveis documentadas em `backend/.env.example`. Nenhum valor
padrão sensível é definido aqui — segredos são sempre exigidos via ambiente.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["production", "test", "development"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: AppEnv = Field(default="development", alias="APP_ENV")

    # Banco de dados. `database_url` é usada pela aplicação (pool assíncrono).
    # `migration_database_url` é opcional e, quando presente, é a URL usada
    # pelo Alembic — permite apontar migrations para uma conexão direta
    # (equivalente ao DIRECT_URL do Prisma) sem trocar a URL da aplicação.
    database_url: str = Field(alias="DATABASE_URL")
    migration_database_url: str | None = Field(default=None, alias="MIGRATION_DATABASE_URL")

    allow_test_db_migrations: bool = Field(default=False, alias="ALLOW_TEST_DB_MIGRATIONS")

    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    # Keycloak / OIDC
    keycloak_issuer: str | None = Field(default=None, alias="KEYCLOAK_ISSUER")
    keycloak_audience: str | None = Field(default=None, alias="KEYCLOAK_AUDIENCE")
    keycloak_jwks_url: str | None = Field(default=None, alias="KEYCLOAK_JWKS_URL")
    keycloak_role_claim: str = Field(default="realm_access.roles", alias="KEYCLOAK_ROLE_CLAIM")
    keycloak_allowed_algorithms: str = Field(default="RS256", alias="KEYCLOAK_ALLOWED_ALGORITHMS")
    jwks_cache_ttl_seconds: int = Field(default=3600, alias="JWKS_CACHE_TTL_SECONDS")

    # Autenticação de desenvolvimento (bypass controlado, nunca em produção).
    dev_auth_enabled: bool = Field(default=False, alias="DEV_AUTH_ENABLED")
    dev_auth_user_email: str = Field(default="dev@example.com", alias="DEV_AUTH_USER_EMAIL")
    dev_auth_user_role: Literal["VIEWER", "ANALYST", "ADMIN"] = Field(
        default="ADMIN", alias="DEV_AUTH_USER_ROLE"
    )

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    import_batch_size: int = Field(default=500, alias="IMPORT_BATCH_SIZE")
    max_import_records_per_batch: int = Field(default=5000, alias="MAX_IMPORT_RECORDS_PER_BATCH")

    # POST /importacoes/{modulo}/arquivos — upload multipart, parsing no servidor.
    max_import_files: int = Field(default=10, alias="MAX_IMPORT_FILES")
    max_import_file_size_bytes: int = Field(default=20 * 1024 * 1024, alias="MAX_IMPORT_FILE_SIZE_BYTES")
    max_import_total_size_bytes: int = Field(default=100 * 1024 * 1024, alias="MAX_IMPORT_TOTAL_SIZE_BYTES")
    max_import_rows_per_file: int = Field(default=200_000, alias="MAX_IMPORT_ROWS_PER_FILE")
    import_file_concurrency: int = Field(default=3, alias="IMPORT_FILE_CONCURRENCY")

    max_page_size: int = Field(default=200, alias="MAX_PAGE_SIZE")
    default_page_size: int = Field(default=50, alias="DEFAULT_PAGE_SIZE")

    seed_test_data: bool = Field(default=False, alias="SEED_TEST_DATA")

    @field_validator("database_url", "migration_database_url")
    @classmethod
    def _require_asyncpg_scheme_for_app_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value.startswith("postgres://"):
            value = "postgresql://" + value[len("postgres://") :]
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def keycloak_allowed_algorithms_list(self) -> list[str]:
        return [alg.strip() for alg in self.keycloak_allowed_algorithms.split(",") if alg.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def sqlalchemy_database_url(self) -> str:
        """URL assíncrona (asyncpg) usada pelo engine da aplicação."""
        return _to_asyncpg_url(self.database_url)

    @property
    def alembic_database_url(self) -> str:
        """URL síncrona (psycopg) usada pelas migrations Alembic."""
        url = self.migration_database_url or self.database_url
        return _to_sync_url(url)


def _asyncpg_compatible_query(query: str) -> str:
    """asyncpg aceita `ssl=<disable|allow|prefer|require|verify-ca|verify-full>`
    (mesmos valores de libpq), mas seu `connect()` não reconhece `sslmode`
    nem `channel_binding` como kwargs — provedores como Neon devolvem a
    `DATABASE_URL` no formato libpq (`sslmode=require&channel_binding=require`),
    que quebra a conexão assíncrona com `TypeError: unexpected keyword
    argument 'sslmode'`. Traduz `sslmode` -> `ssl` e descarta
    `channel_binding` (recurso de libpq, sem equivalente no asyncpg). A URL
    síncrona usada pelo Alembic (`_to_sync_url`, via psycopg) não passa por
    aqui e continua aceitando os parâmetros originais sem tradução."""
    pairs = parse_qsl(query, keep_blank_values=True)
    translated = [
        ("ssl", value) if key == "sslmode" else (key, value)
        for key, value in pairs
        if key != "channel_binding"
    ]
    return urlencode(translated)


def _to_asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://") or url.startswith("sqlite+aiosqlite://"):
        return url
    if url.startswith("postgresql://"):
        async_url = "postgresql+asyncpg://" + url[len("postgresql://") :]
        parts = urlsplit(async_url)
        return urlunsplit(parts._replace(query=_asyncpg_compatible_query(parts.query)))
    if url.startswith("sqlite://"):
        return "sqlite+aiosqlite://" + url[len("sqlite://") :]
    return url


def _to_sync_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg://" + url[len("postgresql+asyncpg://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
