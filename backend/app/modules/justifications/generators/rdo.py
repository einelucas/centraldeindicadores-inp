"""Gerador de sugestão de justificativa do RDO. Porte literal de
`src/features/justifications/generators/rdo.ts`."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.modules.justifications.formatting import format_pt_br
from app.modules.justifications.schemas import EvidenceItem, JustificationStatus, SourceImportIn
from app.modules.justifications.types import Suggestion
from app.modules.rdo.types import STATUS_APROVADO, STATUS_PREENCHENDO, STATUS_REVISAR, RdoNormalizedRecord
from app.shared.dates import MONTH_NAMES_FULL

__all__ = ["generate_rdo_justification"]


@dataclass(slots=True)
class _RankedCause:
    name: str
    pending: int
    total: int
    adherence: float


def _pct(value: float) -> str:
    return f"{format_pt_br(value * 100, 1)}%"


def _rank_by(
    rows: list[RdoNormalizedRecord], read_name: Callable[[RdoNormalizedRecord], str | None]
) -> list[_RankedCause]:
    grouped: dict[str, dict[str, int]] = {}
    for row in rows:
        raw_name = read_name(row)
        name = raw_name.strip() if raw_name else ""
        if not name:
            continue
        current = grouped.setdefault(name, {"pending": 0, "total": 0, "approved": 0})
        current["total"] += 1
        if row.status_descricao == STATUS_APROVADO:
            current["approved"] += 1
        else:
            current["pending"] += 1

    causes = [
        _RankedCause(
            name=name, pending=v["pending"], total=v["total"],
            adherence=(v["approved"] / v["total"]) if v["total"] else 0.0,
        )
        for name, v in grouped.items()
    ]
    causes = [c for c in causes if c.pending > 0]
    causes.sort(key=lambda c: (-c.pending, c.adherence, c.name))
    return causes[:3]


def generate_rdo_justification(
    *,
    records: list[RdoNormalizedRecord],
    previous_records: list[RdoNormalizedRecord],
    year: int,
    month: int,
    threshold: float,
    excluded_units: list[str],
    source_import: SourceImportIn | None,
) -> Suggestion:
    excluded = {u.strip() for u in excluded_units}
    rows = [r for r in records if r.empresa_nome.strip() not in excluded]
    previous_rows = [r for r in previous_records if r.empresa_nome.strip() not in excluded]

    approved = sum(1 for r in rows if r.status_descricao == STATUS_APROVADO)
    review = sum(1 for r in rows if r.status_descricao == STATUS_REVISAR)
    filling = sum(1 for r in rows if r.status_descricao == STATUS_PREENCHENDO)
    other_pending = len(rows) - approved - review - filling
    adherence = (approved / len(rows)) if rows else None

    previous_approved = sum(1 for r in previous_rows if r.status_descricao == STATUS_APROVADO)
    previous_adherence = (previous_approved / len(previous_rows)) if previous_rows else None

    units = _rank_by(rows, lambda r: r.empresa_nome)
    groups = _rank_by(rows, lambda r: r.grupo)
    disciplines = _rank_by(rows, lambda r: r.disciplina)
    month_name = MONTH_NAMES_FULL[month - 1] if 1 <= month <= 12 else f"Mês {month}"

    if adherence is None:
        return Suggestion(
            module="rdo", year=year, month=month, result=None, target=threshold, status="NO_DATA",
            evidence=[],
            suggested_text=(
                f"Não há RDOs válidos em {month_name}/{year} para gerar uma análise baseada em dados."
            ),
            source_import=source_import,
        )

    gap = adherence - threshold
    status: JustificationStatus = "ON_TARGET" if gap >= 0 else "BELOW_TARGET"
    evidence = [
        EvidenceItem(
            label="Resultado do mês", value=_pct(adherence),
            detail=f"{approved} de {len(rows)} RDOs aprovados · meta {_pct(threshold)}",
        ),
        EvidenceItem(
            label="RDOs ainda não aprovados", value=str(len(rows) - approved),
            detail=(
                f"{review} para revisão · {filling} em preenchimento"
                + (f" · {other_pending} em outros status" if other_pending > 0 else "")
            ),
        ),
    ]
    if previous_adherence is not None:
        variation = adherence - previous_adherence
        evidence.append(
            EvidenceItem(
                label="Variação mensal",
                value=f"{'+' if variation >= 0 else ''}{format_pt_br(variation * 100, 1)} p.p.",
                detail=f"mês anterior: {_pct(previous_adherence)}",
            )
        )
    if units:
        evidence.append(
            EvidenceItem(
                label="Maior concentração", value=units[0].name,
                detail=f"{units[0].pending} não aprovado(s) de {units[0].total}",
            )
        )

    gap_line = _pct(gap) + " acima ou no limite da meta" if gap >= 0 else _pct(abs(gap)) + " abaixo da meta"
    lines = [
        f"Em {month_name}/{year}, a aderência de aprovação dos RDOs foi de {_pct(adherence)} "
        f"({approved} de {len(rows)}), frente à meta de {_pct(threshold)}. O resultado ficou {gap_line}.",
        f"No fechamento do período, {len(rows) - approved} RDO(s) ainda não estavam aprovados: "
        f"{review} em “Revisar Relatório”, {filling} em “Preenchendo Relatório”"
        + (f" e {other_pending} em outros status" if other_pending > 0 else "") + ".",
    ]
    if units:
        lines.append(
            "As maiores concentrações de RDOs não aprovados ocorreram em: "
            + "; ".join(f"{u.name} ({u.pending} de {u.total}; aderência {_pct(u.adherence)})" for u in units)
            + "."
        )
    if groups:
        lines.append(
            "Por grupo, destacaram-se: " + "; ".join(f"{g.name} ({g.pending})" for g in groups) + "."
        )
    if disciplines:
        lines.append(
            "Por disciplina, destacaram-se: "
            + "; ".join(f"{d.name} ({d.pending})" for d in disciplines) + "."
        )
    if previous_adherence is not None:
        variation = adherence - previous_adherence
        direction = "avanço" if variation >= 0 else "recuo"
        lines.append(
            f"Em comparação ao mês anterior ({_pct(previous_adherence)}), houve {direction} de "
            f"{format_pt_br(abs(variation) * 100, 1)} ponto(s) percentual(is)."
        )
    lines.append(
        "Os dados identificam onde os RDOs pendentes estão concentrados; o contexto operacional da "
        "ocorrência deve ser complementado pelo responsável antes do salvamento."
    )

    return Suggestion(
        module="rdo", year=year, month=month, result=adherence, target=threshold, status=status,
        evidence=evidence, suggested_text="\n\n".join(lines), source_import=source_import,
    )
