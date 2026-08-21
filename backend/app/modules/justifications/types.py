"""Tipo de retorno comum aos 5 geradores de sugestão de justificativa.
Porte de `JustificationSuggestion` (`src/features/justifications/types.ts`)."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.justifications.schemas import EvidenceItem, JustificationStatus, SourceImportIn


@dataclass(slots=True)
class Suggestion:
    module: str
    year: int
    month: int
    result: float | None
    target: float | None
    status: JustificationStatus
    evidence: list[EvidenceItem]
    suggested_text: str
    source_import: SourceImportIn | None
