"""Schemas Pydantic das rotas de justificativas. Porte de
`src/app/api/justificativas/**` (CRUD genérico) e redesenho decorrente do
desacoplamento de `GET /justificativas/sugestao` — ver `router.py` e o
resumo da tarefa para a justificativa completa."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.shared.schema import CamelModel

JUSTIFICATION_MODULES: tuple[str, ...] = ("rdo", "idp", "rnc", "cinco-s", "taxa-acidentes")

JustificationModule = Literal["rdo", "idp", "rnc", "cinco-s", "taxa-acidentes"]
JustificationStatus = Literal["BELOW_TARGET", "ON_TARGET", "NO_DATA"]


class EvidenceItem(CamelModel):
    label: str
    value: str
    detail: str | None = None


class SourceImportIn(CamelModel):
    id: str
    imported_at: datetime | None = None


class NameOut(CamelModel):
    name: str


class JustificationOut(CamelModel):
    id: str
    module: str
    year: int
    month: int
    result: float | None
    target: float | None
    status: str | None
    evidence: list[EvidenceItem]
    suggested_text: str | None
    text: str
    source_import_id: str | None
    source_imported_at: datetime | None
    created_at: datetime
    updated_at: datetime
    created_by: NameOut | None
    updated_by: NameOut | None


class JustificationListOut(CamelModel):
    records: list[JustificationOut]


class SaveJustificationIn(CamelModel):
    module: JustificationModule
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    text: str = Field(min_length=1, max_length=10_000)
    suggested_text: str | None = Field(default=None, max_length=10_000)
    result: float | None = None
    target: float | None = None
    status: JustificationStatus | None = None
    evidence: list[EvidenceItem]
    source_import: SourceImportIn | None = None

    @field_validator("text")
    @classmethod
    def _trim_text(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("String must contain at least 1 character(s)")
        return trimmed


class SaveJustificationOut(CamelModel):
    record: JustificationOut


class DeleteJustificationOut(CamelModel):
    ok: bool = True


class SuggestionOut(CamelModel):
    module: str
    year: int
    month: int
    result: float | None
    target: float | None
    status: JustificationStatus
    evidence: list[EvidenceItem]
    suggested_text: str
    source_import: SourceImportIn | None


class SuggestionResponseOut(CamelModel):
    suggestion: SuggestionOut
