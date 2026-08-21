"""Gerador de sugestão de justificativa do 5S. Porte literal de
`src/features/justifications/generators/cinco-s.ts`."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.cinco_s.calculations import aderencia_area
from app.modules.cinco_s.types import FiveSResult, FiveSUnitMonth
from app.modules.justifications.formatting import format_pt_br
from app.modules.justifications.schemas import EvidenceItem, JustificationStatus, SourceImportIn
from app.modules.justifications.types import Suggestion
from app.shared.dates import MONTH_NAMES_FULL
from app.shared.units import format_unit_label

__all__ = ["generate_five_s_justification"]


@dataclass(slots=True)
class _AreaDeviation:
    unit: str
    division: str
    area: str
    adherence: float
    target: float
    score: float


@dataclass(slots=True)
class _DivisionSummary:
    name: str
    adherence: float
    areas: int
    below: int


def _pct(value: float) -> str:
    return f"{format_pt_br(value * 100, 1)}%"


def _result_units(result: FiveSResult, year: int, month: int) -> list[FiveSUnitMonth]:
    return [u for u in result.unit_months if u.year == year and u.month == month and not u.excluded]


def generate_five_s_justification(
    *,
    result: FiveSResult,
    previous_result: FiveSResult,
    year: int,
    month: int,
    source_import: SourceImportIn | None,
) -> Suggestion:
    units = _result_units(result, year, month)
    previous_units = _result_units(
        previous_result, previous_result.latest_year or year, previous_result.latest_month or month
    )
    month_name = MONTH_NAMES_FULL[month - 1] if 1 <= month <= 12 else f"Mês {month}"
    general = (sum(u.aderencia for u in units) / len(units)) if units else None

    if general is None:
        return Suggestion(
            module="cinco-s", year=year, month=month, result=None, target=result.threshold,
            status="NO_DATA", evidence=[],
            suggested_text=(
                f"Não há auditorias 5S de unidades incluídas em {month_name}/{year} para gerar uma "
                "análise baseada em dados."
            ),
            source_import=source_import,
        )

    status: JustificationStatus = "ON_TARGET" if general >= result.threshold else "BELOW_TARGET"
    units_below_target = sorted(
        (u for u in units if u.aderencia < result.threshold),
        key=lambda u: (u.aderencia, u.unit),
    )

    area_deviations = sorted(
        (
            _AreaDeviation(
                unit=u.unit, division=(area.divisao or "").strip() or "Sem divisão", area=area.area,
                adherence=aderencia_area(area), target=area.meta, score=area.nota,
            )
            for u in units
            for area in u.areas
        ),
        key=lambda d: (d.adherence, d.unit, d.area),
    )
    area_deviations = [d for d in area_deviations if d.adherence < result.threshold]

    division_sums: dict[str, list[float]] = {}
    for u in units:
        for area in u.areas:
            name = (area.divisao or "").strip() or "Sem divisão"
            totals = division_sums.setdefault(name, [0.0, 0.0, 0.0])  # [sum, count, below]
            adherence = aderencia_area(area)
            totals[0] += adherence
            totals[1] += 1
            if adherence < result.threshold:
                totals[2] += 1
    critical_divisions = sorted(
        (
            _DivisionSummary(
                name=name, adherence=(totals[0] / totals[1]) if totals[1] else 0.0,
                areas=int(totals[1]), below=int(totals[2]),
            )
            for name, totals in division_sums.items()
        ),
        key=lambda d: (d.adherence, d.name),
    )
    critical_divisions = [d for d in critical_divisions if d.adherence < result.threshold][:3]

    previous_general = (
        (sum(u.aderencia for u in previous_units) / len(previous_units)) if previous_units else None
    )

    evidence = [
        EvidenceItem(
            label="Aderência geral", value=_pct(general),
            detail=f"{len(units)} unidade(s) incluída(s) · meta {_pct(result.threshold)}",
        ),
        EvidenceItem(
            label="Unidades abaixo da meta", value=str(len(units_below_target)),
            detail=f"{len(units)} unidade(s) auditada(s) e incluída(s)",
        ),
        EvidenceItem(
            label="Áreas abaixo da meta", value=str(len(area_deviations)),
            detail=f"{sum(len(u.areas) for u in units)} área(s) avaliada(s)",
        ),
    ]
    if previous_general is not None:
        variation = general - previous_general
        evidence.append(
            EvidenceItem(
                label="Variação mensal",
                value=f"{'+' if variation >= 0 else ''}{format_pt_br(variation * 100, 1)} p.p.",
                detail=f"mês anterior: {_pct(previous_general)}",
            )
        )

    gap = general - result.threshold
    lines = [
        f"Em {month_name}/{year}, a aderência geral do 5S foi de {_pct(general)}, frente à meta de "
        f"{_pct(result.threshold)}. O resultado ficou "
        + (f"{_pct(gap)} acima ou no limite da meta" if gap >= 0 else f"{_pct(abs(gap))} abaixo da meta")
        + f", considerando {len(units)} unidade(s) incluída(s).",
    ]
    if units_below_target:
        lines.append(
            "As menores aderências por unidade foram: "
            + "; ".join(
                f"{format_unit_label(u.unit)} ({_pct(u.aderencia)}; "
                f"{sum(1 for a in u.areas if aderencia_area(a) < result.threshold)} de {len(u.areas)} "
                "área(s) abaixo da meta)"
                for u in units_below_target[:3]
            )
            + "."
        )
    else:
        lines.append("Nenhuma unidade incluída ficou abaixo da meta no período analisado.")

    if area_deviations:
        lines.append(
            "As áreas com menor aderência foram: "
            + "; ".join(
                f"{format_unit_label(d.unit)} — {d.division} / {d.area} ({_pct(d.adherence)}; "
                f"nota {format_pt_br(d.score, 1)} de meta {format_pt_br(d.target, 1)})"
                for d in area_deviations[:5]
            )
            + "."
        )
    if critical_divisions:
        lines.append(
            "Por divisão, os menores resultados médios foram: "
            + "; ".join(
                f"{d.name} ({_pct(d.adherence)}; {d.below} de {d.areas} área(s) abaixo da meta)"
                for d in critical_divisions
            )
            + "."
        )
    if previous_general is not None:
        variation = general - previous_general
        direction = "avançou" if variation >= 0 else "recuou"
        lines.append(
            f"Em comparação ao mês anterior ({_pct(previous_general)}), a aderência {direction} "
            f"{format_pt_br(abs(variation) * 100, 1)} ponto(s) percentual(is)."
        )
    excluded_count = sum(
        1 for u in result.unit_months if u.year == year and u.month == month and u.excluded
    )
    if excluded_count:
        lines.append(
            f"{excluded_count} unidade(s) ignorada(s) ficou(ram) fora do resultado e desta análise."
        )
    lines.append(
        "A análise identifica onde as notas baixas estão concentradas; o motivo operacional das não "
        "conformidades deve ser confirmado e complementado pelo responsável antes do salvamento."
    )

    return Suggestion(
        module="cinco-s", year=year, month=month, result=general, target=result.threshold, status=status,
        evidence=evidence, suggested_text="\n\n".join(lines), source_import=source_import,
    )
