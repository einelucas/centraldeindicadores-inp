from __future__ import annotations

import asyncio
import os
from pathlib import Path


SOURCE_ENV = Path(r"C:\Users\lucas.pinheiro\Documents\central-nuxt\backend\.env")


def read_database_url(path: Path) -> str:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if raw_line.startswith("DATABASE_URL="):
            return raw_line.partition("=")[2].strip().strip('"').strip("'")
    raise RuntimeError("DATABASE_URL de origem ausente")


os.environ["DATABASE_URL"] = read_database_url(SOURCE_ENV)
os.environ["APP_ENV"] = "test"

from app.core.database import SessionLocal  # noqa: E402
from app.modules.dashboard.service import list_available_periods  # noqa: E402


async def main() -> None:
    async with SessionLocal() as session:
        periods = await list_available_periods(session)
        for period in periods:
            print(period)


asyncio.run(main())
