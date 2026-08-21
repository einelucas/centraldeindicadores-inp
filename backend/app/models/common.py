"""Tipos e helpers comuns aos modelos SQLAlchemy."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import MappedColumn, mapped_column


# Prisma mapeia `String @id @default(uuid())` para uma coluna TEXT (não o tipo
# nativo `uuid` do Postgres) e gera o UUID no cliente, não no banco — a mesma
# estratégia é replicada aqui para preservar o tipo real da coluna.
def uuid_pk() -> MappedColumn[str]:
    return mapped_column(
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False,
    )


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


# `TIMESTAMP(3)` sem timezone — mesmo tipo que o Prisma gera por padrão para `DateTime`.
Timestamp3 = TIMESTAMP(precision=3, timezone=False)

__all__ = ["DateTime", "Timestamp3", "uuid_pk", "utcnow"]
