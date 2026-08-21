"""Modelos SQLAlchemy — mapeiam 1:1 as tabelas reais do PostgreSQL criadas
originalmente pelo Prisma (`prisma/schema.prisma` / `prisma/migrations/0_baseline`).

Nomes de tabela e coluna são preservados EXATAMENTE (mesma capitalização,
mesmos tipos) para permitir migração futura de dados reais sem conversão.
Não usar `@@map`-like renames — os nomes PascalCase/camelCase são intencionais
e replicam o schema Prisma, não a convenção usual do Python.
"""

from app.models.audit import AuditLog
from app.models.imports import ImportBatch, ImportError, ImportJob, ImportStatus
from app.models.indicators import IndicatorJustification, IndicatorPublication, IndicatorResult
from app.models.records import (
    AccidentMonthlyRecord,
    AccidentUnitRecord,
    FiveSRecord,
    IdpRecord,
    IdpRsoRecord,
    RdoRecord,
    RncRecord,
    ScorecardSnapshot,
)
from app.models.settings import AppSetting
from app.models.user import Account, Role, Session, User, Verification

__all__ = [
    "AuditLog",
    "ImportBatch",
    "ImportError",
    "ImportJob",
    "ImportStatus",
    "IndicatorJustification",
    "IndicatorPublication",
    "IndicatorResult",
    "AccidentMonthlyRecord",
    "AccidentUnitRecord",
    "FiveSRecord",
    "IdpRecord",
    "IdpRsoRecord",
    "RdoRecord",
    "RncRecord",
    "ScorecardSnapshot",
    "AppSetting",
    "Account",
    "Role",
    "Session",
    "User",
    "Verification",
]
