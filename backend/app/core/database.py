"""Engine e sessão SQLAlchemy assíncronos (asyncpg)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def create_engine() -> AsyncEngine:
    settings = get_settings()
    # `NullPool` em testes: cada checkout abre uma conexão asyncpg nova,
    # sempre presa ao event loop atualmente ativo. Com pool persistente
    # (AsyncAdaptedQueuePool), uma conexão criada em um teste/loop pode ser
    # reaproveitada em outro loop do pytest-asyncio, e o asyncpg rejeita a
    # operação ("attached to a different loop"). Em produção (um único loop
    # de vida longa, o do próprio servidor Uvicorn) o pool persistente é
    # seguro e mais eficiente. Nota: `QueuePool` puro NÃO é compatível com
    # engines assíncronas do SQLAlchemy (`ArgumentError` no boot) — a
    # variante correta é `AsyncAdaptedQueuePool`.
    pool_class = NullPool if settings.app_env == "test" else AsyncAdaptedQueuePool
    engine_kwargs: dict = {"future": True}
    if pool_class is AsyncAdaptedQueuePool:
        engine_kwargs.update(pool_pre_ping=True, pool_size=10, max_overflow=5)
    # `command_timeout` do asyncpg: cancela qualquer statement pendurado após
    # N segundos em vez de travar a conexão indefinidamente — uma query presa
    # (ou um teste que nunca fecha a sessão) vira um erro rápido e visível em
    # vez de um hang silencioso que bloqueia toda a suíte via lock do Postgres.
    return create_async_engine(
        settings.sqlalchemy_database_url,
        poolclass=pool_class,
        connect_args={"timeout": 10, "command_timeout": 20},
        **engine_kwargs,
    )


engine: AsyncEngine = create_engine()

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Dependência FastAPI: uma sessão por requisição, com rollback em erro."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_ready() -> bool:
    """Usado por `/health/ready` — `SELECT 1` simples."""
    from sqlalchemy import text

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        return result.scalar_one() == 1
