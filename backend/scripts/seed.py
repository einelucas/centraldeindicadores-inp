"""Seed idempotente — configurações oficiais + usuário de teste.

Porta `prisma/seed.ts`. NUNCA deve ser habilitado automaticamente em
produção — recusa-se a rodar quando `APP_ENV == "production"`, a menos que
`SEED_TEST_DATA=true` seja passado explicitamente E o ambiente não seja
produção (dupla trava).

Uso:
    python scripts/seed.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.auth import KEYCLOAK_AUTH_PROVIDER  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.settings import AppSetting  # noqa: E402
from app.models.user import Role, User  # noqa: E402

# Mesmos valores padrão de `prisma/seed.ts` / `docs/database.md`.
DEFAULT_SETTINGS: list[tuple[str, object]] = [
    ("rdo.target", 0.8),
    ("idp.target", 0.9),
    ("idp.excludedDisciplines", ["10 _ Fornecimentos", "09 _ Projetos"]),
    ("fiveS.target", 0.9),
    ("rnc.maxPrazoDias", 15),
    ("fiveS.excludedUnits", ["SP", "CSC"]),
    ("taxa-acidentes.target", 7.5),
]

# Unidades operacionais conhecidas — ver app/shared/units.py (fonte de verdade
# do código; aqui apenas garantimos que o seed as menciona para referência).
KNOWN_UNIT_CODES = ["LEM", "MTU", "RVD", "BLS", "SNP", "DRD", "RDN", "SDR"]

TEST_USER_EXTERNAL_ID = "seed:test-admin"
TEST_USER_EMAIL = "teste.admin@central-indicadores.local"


async def main() -> None:
    settings = get_settings()
    if settings.is_production and not settings.seed_test_data:
        print("Seed de teste recusado: APP_ENV=production e SEED_TEST_DATA != true.")
        return

    async with SessionLocal() as session:
        for key, value in DEFAULT_SETTINGS:
            stmt = (
                pg_insert(AppSetting)
                .values(key=key, value=value)
                .on_conflict_do_nothing(index_elements=["key"])
            )
            await session.execute(stmt)
        print(f"OK: {len(DEFAULT_SETTINGS)} configurações garantidas (idempotente).")

        result = await session.execute(
            select(User).where(
                User.authProvider == KEYCLOAK_AUTH_PROVIDER,
                User.externalUserId == TEST_USER_EXTERNAL_ID,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            session.add(
                User(
                    name="Administrador de Teste",
                    email=TEST_USER_EMAIL,
                    emailVerified=True,
                    role=Role.ADMIN,
                    active=True,
                    authProvider=KEYCLOAK_AUTH_PROVIDER,
                    externalUserId=TEST_USER_EXTERNAL_ID,
                )
            )
            print(f"OK: usuário de teste criado ({TEST_USER_EMAIL}).")
        else:
            print(f"OK: usuário de teste já existe ({TEST_USER_EMAIL}) — nada a fazer.")

        await session.commit()

    print(f"Unidades conhecidas (referência, não persistidas em tabela própria): {KNOWN_UNIT_CODES}")


if __name__ == "__main__":
    asyncio.run(main())
