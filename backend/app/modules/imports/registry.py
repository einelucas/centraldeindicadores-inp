"""Registro dos módulos atendidos pelo motor de importação incremental.

Porte de `src/server/modules/registry.ts`. Cada módulo (rdo/idp/rnc/cinco_s)
se registra chamando `register_module(...)` a partir do próprio
`app/modules/<modulo>/router.py`, no import — nunca editar este arquivo para
adicionar um módulo nele diretamente (evita conflito entre módulos
implementados em paralelo). `app/api/v1/router.py` garante que todos os
módulos sejam importados antes de qualquer rota de importação ser atendida.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.incremental_upsert import IncrementalRecord, RecordDelegate

ToIncrementalRecords = Callable[[list[Any]], tuple[list[IncrementalRecord], int]]
DelegateFactory = Callable[[AsyncSession], RecordDelegate]
RecalcIndicators = Callable[[AsyncSession], Awaitable[None]]


@dataclass(slots=True)
class FileRowError:
    row: int | None
    field: str | None
    message: str


@dataclass(slots=True)
class FileImportFileResult:
    file_name: str
    found: int
    accepted: int
    rejected: int
    errors: list[FileRowError] = field(default_factory=list)


@dataclass(slots=True)
class FileImportOutcome:
    """Resultado consolidado de `POST /importacoes/{modulo}/arquivos` — cada
    módulo monta o seu (parse + dedup entre arquivos + `to_incremental_records`
    + `bulk_upsert` + `recalc_indicators`, tudo dentro da mesma transação)."""

    inserted: int = 0
    updated: int = 0
    ignored: int = 0
    rejected: int = 0
    files: list[FileImportFileResult] = field(default_factory=list)


FileImportRunner = Callable[[AsyncSession, list[tuple[str, bytes]], str], Awaitable[FileImportOutcome]]


@dataclass(frozen=True, slots=True)
class ModuleDefinition:
    to_incremental_records: ToIncrementalRecords
    delegate_factory: DelegateFactory
    recalc_indicators: RecalcIndicators
    file_import: FileImportRunner | None = None
    """Só populado pelos módulos já migrados para `POST
    /importacoes/{modulo}/arquivos` (RDO na Fase A) — `None` faz o endpoint
    novo devolver 501 para módulos que ainda usam só o fluxo antigo."""


_REGISTRY: dict[str, ModuleDefinition] = {}


def register_module(name: str, definition: ModuleDefinition) -> None:
    _REGISTRY[name] = definition


def get_module_definition(name: str) -> ModuleDefinition | None:
    return _REGISTRY.get(name)


def migrated_modules() -> list[str]:
    return list(_REGISTRY.keys())
