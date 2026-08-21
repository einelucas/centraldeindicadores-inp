"""Gerador de sugestão de justificativa do IDP/RSO. Porte literal de
`src/features/justifications/generators/idp.ts`."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.idp.types import IdpResult
from app.modules.justifications.formatting import format_pt_br
from app.modules.justifications.schemas import EvidenceItem, JustificationStatus, SourceImportIn
from app.modules.justifications.types import Suggestion
from app.shared.dates import MONTH_NAMES_FULL

__all__ = ["generate_idp_justification"]


@dataclass(slots=True)
class _PhaseDeviation:
    unit: str
    phase: str
    planned: float
    actual: float
    gap: float


def _pct(value: float) -> str:
    return f"{format_pt_br(value * 100, 1)}%"


def _accumulated(value: float) -> str:
    return f"{format_pt_br(value, 1)}%"


def generate_idp_justification(
    *, result: IdpResult, previous_result: IdpResult, source_import: SourceImportIn | None
) -> Suggestion:
    included_units = [u for u in result.unit_rows if not u.excluded]
    previous_included_units = [u for u in previous_result.unit_rows if not u.excluded]
    month_name = (
        MONTH_NAMES_FULL[result.selected_month - 1]
        if 1 <= result.selected_month <= 12
        else f"Mês {result.selected_month}"
    )

    if not included_units:
        return Suggestion(
            module="idp", year=result.selected_year, month=result.selected_month, result=None,
            target=result.threshold, status="NO_DATA", evidence=[],
            suggested_text=(
                f"Não há RSOs ativos de unidades incluídas em {month_name}/{result.selected_year} "
                "para gerar uma análise baseada em dados."
            ),
            source_import=source_import,
        )

    # Guardado pelo chamador (aderencia_geral só é None quando nenhuma
    # unidade incluída tem aderência válida — impossível aqui, já que
    # `included_units` não está vazio e cada unidade só fica sem aderência
    # se seu previsto for zero; nesse caso `aderencia_geral` seria None e
    # cairíamos aqui de qualquer forma).
    if result.aderencia_geral is None:
        return Suggestion(
            module="idp", year=result.selected_year, month=result.selected_month, result=None,
            target=result.threshold, status="NO_DATA", evidence=[],
            suggested_text=(
                f"Não há RSOs ativos de unidades incluídas em {month_name}/{result.selected_year} "
                "para gerar uma análise baseada em dados."
            ),
            source_import=source_import,
        )

    gap = result.aderencia_geral - result.threshold
    status: JustificationStatus = "ON_TARGET" if gap >= 0 else "BELOW_TARGET"

    units_below_target = sorted(
        (u for u in included_units if u.aderencia is not None and u.aderencia < result.threshold),
        key=lambda u: (u.aderencia if u.aderencia is not None else 0.0, u.unit),
    )[:3]
    disciplines_below_target = sorted(
        (
            d for d in result.discipline_rows
            if d.aderencia is not None and d.aderencia < result.threshold
        ),
        key=lambda d: (d.aderencia if d.aderencia is not None else float("inf"), d.disciplina),
    )[:3]
    phase_deviations = sorted(
        (
            _PhaseDeviation(
                unit=u.unit, phase=p.label, planned=p.prev_acum, actual=p.real_acum,
                gap=p.prev_acum - p.real_acum,
            )
            for u in included_units
            for p in u.phases
            if p.prev_acum - p.real_acum > 0
        ),
        key=lambda d: (-d.gap, d.unit),
    )[:3]
    previous_adherence = previous_result.aderencia_geral if previous_included_units else None

    evidence = [
        EvidenceItem(
            label="Aderência geral", value=_pct(result.aderencia_geral),
            detail=f"{len(included_units)} RSO(s) ativo(s) incluído(s) · meta {_pct(result.threshold)}",
        ),
        EvidenceItem(
            label="Unidades abaixo da meta",
            value=str(
                sum(1 for u in included_units if u.aderencia is not None and u.aderencia < result.threshold)
            ),
            detail=f"{len(included_units)} unidade(s) considerada(s) no resultado",
        ),
    ]
    if previous_adherence is not None:
        variation = result.aderencia_geral - previous_adherence
        evidence.append(
            EvidenceItem(
                label="Variação mensal",
                value=f"{'+' if variation >= 0 else ''}{format_pt_br(variation * 100, 1)} p.p.",
                detail=f"mês anterior: {_pct(previous_adherence)}",
            )
        )
    if phase_deviations:
        top = phase_deviations[0]
        evidence.append(
            EvidenceItem(
                label="Maior desvio de fase", value=f"{format_pt_br(top.gap, 1)} p.p.",
                detail=f"{top.unit} · {top.phase}",
            )
        )

    lines = [
        f"Em {month_name}/{result.selected_year}, a aderência geral do IDP foi de "
        f"{_pct(result.aderencia_geral)}, frente à meta de {_pct(result.threshold)}. O resultado ficou "
        + (f"{_pct(gap)} acima ou no limite da meta" if gap >= 0 else f"{_pct(abs(gap))} abaixo da meta")
        + f", considerando o maior RSO de cada uma das {len(included_units)} unidade(s) incluída(s) "
        "na competência.",
    ]

    if units_below_target:
        lines.append(
            "As menores aderências por unidade foram: "
            + "; ".join(
                f"{u.unit} ({_pct(u.aderencia or 0.0)}; previsto acumulado médio "
                f"{_accumulated(u.prev_acum)} e realizado {_accumulated(u.real_acum)}; RSO {u.rso_numero})"
                for u in units_below_target
            )
            + "."
        )
    else:
        lines.append("Nenhuma unidade incluída ficou abaixo da meta na competência analisada.")

    if disciplines_below_target:
        lines.append(
            "Entre as disciplinas consideradas, as menores aderências foram: "
            + "; ".join(
                f"{d.disciplina} ({_pct(d.aderencia or 0.0)}; "
                f"previsto médio {_accumulated(d.prev_avg or 0.0)} "
                f"e realizado {_accumulated(d.real_avg or 0.0)})"
                for d in disciplines_below_target
            )
            + "."
        )

    if phase_deviations:
        lines.append(
            "Os maiores desvios entre previsto e realizado nas fases dos RSOs ativos foram: "
            + "; ".join(
                f"{p.unit} — {p.phase} ({_accumulated(p.planned)} previsto e {_accumulated(p.actual)} "
                f"realizado; diferença de {format_pt_br(p.gap, 1)} p.p.)"
                for p in phase_deviations
            )
            + "."
        )

    if previous_adherence is not None:
        variation = result.aderencia_geral - previous_adherence
        direction = "avanço" if variation >= 0 else "recuo"
        lines.append(
            f"Em comparação ao mês anterior ({_pct(previous_adherence)}), houve {direction} de "
            f"{format_pt_br(abs(variation) * 100, 1)} ponto(s) percentual(is)."
        )

    excluded_count = sum(1 for u in result.unit_rows if u.excluded)
    if excluded_count:
        lines.append(
            f"{excluded_count} unidade(s) marcada(s) como ignorada(s) permaneceu(ram) fora do "
            "resultado e desta análise."
        )
    lines.append(
        "Os dados mostram onde o desvio de cronograma está concentrado, mas não comprovam sua causa "
        "operacional; esse contexto deve ser confirmado e complementado pelo responsável antes do "
        "salvamento."
    )

    return Suggestion(
        module="idp", year=result.selected_year, month=result.selected_month,
        result=result.aderencia_geral, target=result.threshold, status=status,
        evidence=evidence, suggested_text="\n\n".join(lines), source_import=source_import,
    )
