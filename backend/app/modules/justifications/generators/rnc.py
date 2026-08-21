"""Gerador de sugestão de justificativa do RNC. Porte literal de
`src/features/justifications/generators/rnc.ts`."""

from __future__ import annotations

from app.modules.justifications.formatting import format_pt_br
from app.modules.justifications.schemas import EvidenceItem, JustificationStatus, SourceImportIn
from app.modules.justifications.types import Suggestion
from app.modules.rnc.types import RncResult
from app.shared.dates import MONTH_NAMES_FULL
from app.shared.units import format_unit_label

__all__ = ["generate_rnc_justification"]


def _days(value: float) -> str:
    return format_pt_br(value, 1)


def generate_rnc_justification(
    *,
    result: RncResult,
    previous_result: RncResult,
    year: int,
    month: int,
    source_import: SourceImportIn | None,
) -> Suggestion:
    current_month = next(
        (m for m in result.months if m.year == year and m.month == month - 1), None
    )
    previous_month = previous_result.months[0] if previous_result.months else None
    month_name = MONTH_NAMES_FULL[month - 1] if 1 <= month <= 12 else f"Mês {month}"

    if current_month is None or current_month.dias_medios is None:
        return Suggestion(
            module="rnc", year=year, month=month, result=None, target=result.meta_dias, status="NO_DATA",
            evidence=[],
            suggested_text=(
                f"Não há RNCs solucionadas com tempo de tratativa válido em {month_name}/{year} "
                "para gerar uma análise de prazo baseada em dados."
            ),
            source_import=source_import,
        )

    average_days = current_month.dias_medios
    status: JustificationStatus = "ON_TARGET" if average_days <= result.meta_dias else "BELOW_TARGET"

    all_units_above_target = sorted(
        (
            u for u in result.units
            if not u.excluded and u.dias_medios is not None and u.dias_medios > result.meta_dias
        ),
        key=lambda u: (-(u.dias_medios or 0.0), u.name),
    )
    units_above_target = all_units_above_target[:3]
    included_units_with_time = [u for u in result.units if not u.excluded and u.tratativas_com_tempo > 0]
    sample_size = sum(u.tratativas_com_tempo for u in included_units_with_time)
    worst_candidates = sorted(
        (u for u in included_units_with_time if u.maior_tempo_tratativa is not None),
        key=lambda u: -(u.maior_tempo_tratativa or 0.0),
    )
    worst_case = worst_candidates[0] if worst_candidates else None

    evidence = [
        EvidenceItem(
            label="Prazo médio do mês", value=f"{_days(average_days)} dias",
            detail=(
                f"meta de até {_days(result.meta_dias)} dias · "
                f"{current_month.solucionados}/{current_month.chamados} solucionada(s)"
            ),
        ),
        EvidenceItem(
            label="Unidades acima da meta", value=str(len(all_units_above_target)),
            detail=f"{len(included_units_with_time)} unidade(s) incluída(s) com tempo válido",
        ),
    ]
    if previous_month is not None and previous_month.dias_medios is not None:
        variation = average_days - previous_month.dias_medios
        evidence.append(
            EvidenceItem(
                label="Variação mensal",
                value=f"{'+' if variation >= 0 else ''}{_days(variation)} dias",
                detail=f"mês anterior: {_days(previous_month.dias_medios)} dias",
            )
        )
    if worst_case is not None and worst_case.maior_tempo_tratativa is not None:
        evidence.append(
            EvidenceItem(
                label="Maior tempo individual", value=f"{_days(worst_case.maior_tempo_tratativa)} dias",
                detail=format_unit_label(worst_case.name),
            )
        )

    difference = average_days - result.meta_dias
    diff_line = (
        f"{_days(abs(difference))} dia(s) abaixo ou no limite da meta"
        if difference <= 0
        else f"{_days(difference)} dia(s) acima da meta"
    )
    lines = [
        f"Em {month_name}/{year}, o prazo médio de resolução das RNCs foi de {_days(average_days)} dias, "
        f"frente à meta de até {_days(result.meta_dias)} dias. O resultado ficou {diff_line}, com "
        f"{current_month.solucionados} de {current_month.chamados} RNC(s) solucionada(s) na coorte do mês.",
    ]

    if units_above_target:
        parts = []
        for u in units_above_target:
            median_text = (
                "sem mediana" if u.dias_medianos is None else f"mediana {_days(u.dias_medianos)} dias"
            )
            offender_text = (
                f"principal ofensor: {u.principal_ofensor} ({u.principal_ofensor_count} RNC(s))"
                if u.principal_ofensor
                else "sem ofensor identificado"
            )
            parts.append(
                f"{format_unit_label(u.name)}: média {_days(u.dias_medios or 0.0)} dias ({median_text}), "
                f"{u.tratadas}/{u.criadas} tratada(s), {offender_text}"
            )
        lines.append("As unidades com média acima da meta foram: " + "; ".join(parts) + ".")
    else:
        lines.append(
            "Nenhuma unidade incluída com tempo de tratativa válido apresentou média acima da meta."
        )

    if worst_case is not None and worst_case.maior_tempo_tratativa is not None:
        lines.append(
            f"O maior tempo individual observado foi de {_days(worst_case.maior_tempo_tratativa)} dias em "
            f"{format_unit_label(worst_case.name)}. A comparação entre média e mediana deve ser usada "
            "para avaliar se poucos casos longos estão elevando o resultado."
        )

    if previous_month is not None and previous_month.dias_medios is not None:
        variation = average_days - previous_month.dias_medios
        direction = "melhorou" if variation <= 0 else "piorou"
        lines.append(
            f"Em comparação ao mês anterior ({_days(previous_month.dias_medios)} dias), o prazo médio "
            f"{direction} {_days(abs(variation))} dia(s)."
        )
    if sample_size < 3:
        lines.append(
            f"A leitura deve ser feita com cautela porque apenas {sample_size} tratativa(s) com tempo "
            "válido compõe(m) as médias por unidade deste mês."
        )
    excluded_count = sum(1 for u in result.units if u.excluded)
    if excluded_count:
        lines.append(
            f"{excluded_count} unidade(s) ignorada(s) ficou(ram) fora do resultado e desta análise."
        )
    lines.append(
        "A análise identifica concentrações e distribuição dos prazos; a causa operacional do atraso "
        "deve ser confirmada e complementada pelo responsável antes do salvamento."
    )

    return Suggestion(
        module="rnc", year=year, month=month, result=average_days, target=result.meta_dias, status=status,
        evidence=evidence, suggested_text="\n\n".join(lines), source_import=source_import,
    )
