"""Fixtures compartilhadas por toda a suíte de testes.

Requer um PostgreSQL real acessível via `DATABASE_URL` (ver `backend/.env`),
com `alembic upgrade head` já aplicado. Não usar SQLite — ver
`docs/backend-migration-decisions.md`.

Padrão de uso em um teste de integração:

    async def test_algo(client, db_session, auth_header):
        response = await client.get("/api/v1/rdo", headers=auth_header("ADMIN"))
        assert response.status_code == 200
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import app.models  # noqa: F401 — garante que todos os modelos estejam registrados
from app.core.database import Base, SessionLocal, engine
from app.main import app as fastapi_app


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    session = SessionLocal()
    try:
        yield session
        await session.rollback()
    finally:
        await session.close()


@pytest_asyncio.fixture(autouse=True)
async def _clean_database() -> AsyncIterator[None]:
    """Limpa todas as tabelas de aplicação após cada teste (banco de teste
    dedicado e efêmero — nunca aponta para produção, ver env.py).

    `lock_timeout` curto: se alguma conexão de um teste anterior ainda
    estiver seguindo uma transação aberta (fixture mal fechada), o TRUNCATE
    falha rápido com um erro claro do Postgres em vez de travar a suíte
    inteira esperando indefinidamente por um lock.
    """
    yield
    table_names = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL lock_timeout = '5s'"))
        await conn.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_header() -> Callable[[str], dict[str, str]]:
    """`auth_header("ADMIN")` -> header Bearer do bypass DEV_AUTH_ENABLED.
    Requer `DEV_AUTH_ENABLED=true` no `.env` de teste (já configurado)."""

    def _make(role: str) -> dict[str, str]:
        return {"Authorization": f"Bearer dev-{role.lower()}"}

    return _make
