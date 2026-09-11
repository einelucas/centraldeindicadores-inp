"""Fixtures compartilhadas por toda a suíte de testes.

Requer um PostgreSQL real DEDICADO a testes, acessível via `DATABASE_URL` em
`backend/.env.test` (nunca `backend/.env` — esse é o arquivo do servidor de
desenvolvimento, com dados reais), com `alembic upgrade head` já aplicado.
Não usar SQLite — ver `docs/backend-migration-decisions.md`.

INCIDENTE (não repita): esta suíte truncava todas as tabelas após cada teste
apontando para o mesmo banco do `.env` usado pelo servidor de desenvolvimento,
porque não havia banco de teste separado. Isso apagou dados reais mais de uma
vez. A partir de agora:
  1. `.env.test` é carregado aqui ANTES de qualquer import de `app.*`, com
     `override=True`, garantindo que a suíte NUNCA herda `DATABASE_URL` do
     `.env` do desenvolvedor mesmo que ambos estejam presentes.
  2. `_clean_database` se recusa a rodar `TRUNCATE` se o banco conectado não
     tiver o sufixo `_test` no nome — trava física contra apontar a suíte
     para o banco real por engano.

Padrão de uso em um teste de integração:

    async def test_algo(client, db_session, auth_header):
        response = await client.get("/api/v1/rdo", headers=auth_header("ADMIN"))
        assert response.status_code == 200
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_ENV_TEST_PATH = Path(__file__).resolve().parent.parent / ".env.test"
if not _ENV_TEST_PATH.is_file():
    raise RuntimeError(
        f"'{_ENV_TEST_PATH}' não encontrado. A suíte de testes recusa-se a "
        "rodar sem um banco de dados dedicado a testes — copie "
        "'.env.test.example' para '.env.test' e ajuste DATABASE_URL para um "
        "banco separado do usado por 'backend/.env'. NUNCA aponte os dois "
        "para o mesmo banco: a suíte trunca todas as tabelas a cada teste."
    )
load_dotenv(_ENV_TEST_PATH, override=True)

import app.models  # noqa: E402,F401 — garante que todos os modelos estejam registrados
from app.core.config import get_settings  # noqa: E402
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402


def _assert_connected_to_test_database(database_name: str) -> None:
    """Última linha de defesa antes de qualquer TRUNCATE.

    Mesmo com `.env.test` carregado corretamente, esta checagem recusa a
    limpeza se o banco conectado não parecer um banco de teste — protege
    contra reconfigurações futuras de `.env.test` que apontem, por engano,
    para o banco real."""
    settings = get_settings()
    if settings.app_env != "test":
        raise RuntimeError(
            f"Recusando TRUNCATE: APP_ENV='{settings.app_env}' (esperado 'test'). "
            "Verifique backend/.env.test."
        )
    if not database_name.endswith("_test"):
        raise RuntimeError(
            f"Recusando TRUNCATE: banco conectado é '{database_name}', que não "
            "termina em '_test'. A suíte de testes só pode truncar um banco "
            "dedicado a testes. Verifique DATABASE_URL em backend/.env.test."
        )


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
        current_db = (await conn.execute(text("SELECT current_database()"))).scalar_one()
        _assert_connected_to_test_database(current_db)
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
