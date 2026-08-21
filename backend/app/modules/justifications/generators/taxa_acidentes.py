"""Gerador de sugestão de justificativa da Taxa de Acidentes. Porte literal
de `src/features/justifications/generators/taxa-acidentes.ts`."""

from __future__ import annotations

from app.modules.justifications.formatting import format_pt_br
from app.modules.justifications.schemas import EvidenceItem, JustificationStatus, SourceImportIn
from app.modules.justifications.types import Suggestion
from app.modules.taxa_acidentes.types import AccidentRateResult
from app.shared.dates import MONTH_NAMES_FULL
from app.shared.units import format_unit_label

__all__ = ["generate_accident_rate_justification"]


def _number(value: float) -> str:
    return format_pt_br(value, 2)


def generate_accident_rate_justification(
    *,
    result: AccidentRateResult,
    previous_result: AccidentRateResult,
    year: int,
    month: int,
    source_import: SourceImportIn | None,
) -> Suggestion:
    current_month = result.monthly[0] if result.monthly else None
    previous_month = previous_result.monthly[0] if previous_result.monthly else None
    month_name = MONTH_NAMES_FULL[month - 1] if 1 <= month <= 12 else f"Mês {month}"

    if current_month is None:
        return Suggestion(
            module="taxa-acidentes", year=year, month=month, result=None, target=result.target,
            status="NO_DATA", evidence=[],
            suggested_text=(
                f"Não há lançamento da taxa de frequência em {month_name}/{year} para gerar uma "
                "análise baseada em dados."
            ),
            source_import=source_import,
        )

    status: JustificationStatus = "ON_TARGET" if current_month.rate <= result.target else "BELOW_TARGET"
    included_units = [u for u in result.units if not u.excluded]
    excluded_unit_count = len({u.unit for u in result.units if u.excluded})
    units_with_accidents = sorted(
        (u for u in included_units if u.caf + u.saf > 0),
        key=lambda u: (-(u.caf + u.saf), -u.caf, format_unit_label(u.unit)),
    )
    unit_accident_total = result.total_unit_caf + result.total_saf
    caf_difference = current_month.caf - result.total_unit_caf
    gap = current_month.rate - result.target

    evidence = [
        EvidenceItem(
            label="Taxa de frequência", value=_number(current_month.rate),
            detail=f"meta de até {_number(result.target)}",
        ),
        EvidenceItem(
            label="Desvio da meta", value=f"{'+' if gap > 0 else ''}{_number(gap)}",
            detail="resultado dentro da meta" if gap <= 0 else "resultado acima da meta",
        ),
        EvidenceItem(
            label="Acidentes CAF", value=str(current_month.caf),
            detail=f"{result.total_unit_caf} CAF distribuído(s) por unidade",
        ),
        EvidenceItem(
            label="Acidentes SAF por unidade", value=str(result.total_saf),
            detail=f"{len(included_units)} unidade(s) incluída(s) com lançamento",
        ),
    ]
    if previous_month is not None:
        variation = current_month.rate - previous_month.rate
        evidence.append(
            EvidenceItem(
                label="Variação mensal da taxa", value=f"{'+' if variation > 0 else ''}{_number(variation)}",
                detail=f"mês anterior: {_number(previous_month.rate)}",
            )
        )

    diff_line = (
        f"{_number(abs(gap))} ponto(s) abaixo ou no limite da meta"
        if gap <= 0
        else f"{_number(gap)} ponto(s) acima da meta"
    )
    lines = [
        f"Em {month_name}/{year}, a taxa de frequência foi de {_number(current_month.rate)}, frente à "
        f"meta de até {_number(result.target)}. O resultado ficou {diff_line}.",
    ]

    if previous_month is not None:
        variation = current_month.rate - previous_month.rate
        direction = "melhorou" if variation <= 0 else "piorou"
        lines.append(
            f"Em comparação ao mês anterior ({_number(previous_month.rate)}), a taxa {direction} "
            f"{_number(abs(variation))} ponto(s)."
        )
    else:
        lines.append("Não há taxa registrada no mês anterior para avaliar a evolução mensal.")

    lines.append(
        f"Foram registrados {current_month.caf} acidente(s) CAF no consolidado mensal. No "
        f"detalhamento das unidades incluídas constam {result.total_unit_caf} CAF e {result.total_saf} "
        f"SAF, totalizando {unit_accident_total} ocorrência(s)."
    )

    if caf_difference != 0:
        lines.append(
            f"Há uma diferença de {abs(caf_difference)} acidente(s) CAF entre o consolidado mensal e a "
            f"soma por unidade ({current_month.caf} contra {result.total_unit_caf}); essa divergência "
            "deve ser conferida antes da apresentação do resultado."
        )

    if units_with_accidents:
        parts = []
        for u in units_with_accidents[:3]:
            total = u.caf + u.saf
            share = (total / unit_accident_total) * 100 if unit_accident_total > 0 else 0.0
            parts.append(
                f"{format_unit_label(u.unit)}: {total} ocorrência(s) ({u.caf} CAF e {u.saf} SAF; "
                f"{_number(share)}% do total por unidade)"
            )
        lines.append(
            "As maiores concentrações de ocorrências no detalhamento por unidade foram: "
            + "; ".join(parts) + "."
        )
    else:
        lines.append(
            "Não há ocorrências CAF ou SAF no detalhamento das unidades incluídas para atribuir "
            "concentração no período."
        )

    if excluded_unit_count:
        lines.append(
            f"{excluded_unit_count} unidade(s) ignorada(s) ficou(ram) fora das somas e da análise de "
            "concentração."
        )
    lines.append(
        "A análise identifica evolução, consistência dos totais e concentração das ocorrências; a "
        "causa operacional dos acidentes deve ser confirmada e complementada pelo responsável antes "
        "do salvamento."
    )

    return Suggestion(
        module="taxa-acidentes", year=year, month=month, result=current_month.rate, target=result.target,
        status=status, evidence=evidence, suggested_text="\n\n".join(lines), source_import=source_import,
    )
