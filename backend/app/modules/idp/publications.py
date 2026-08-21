"""Payload de publicação do IDP/RSO. Porte literal de
`toIdpPublishedPayload` (`src/features/idp/publications/index.ts`).

**Correção aplicada em relação ao HEAD** (ver decisions.md §4.2.5): no TS
original, a guarda de pré-condição só checa `!activeDocuments`, mas NÃO
`totalPrevistoMedio <= 0` na rota (`POST /publicacoes/idp`) antes de chamar
esta função — se todas as unidades ativas estiverem excluídas,
`toIdpPublishedPayload` lança um `Error` genérico que a rota não intercepta,
caindo num 500 sem a mensagem específica. Aqui a mesma checagem
(`total_previsto_medio <= 0`) já dispara `DomainError` (→ 422, mensagem
preservada), tanto nesta função quanto na rota — nunca um 500 escondendo a
mensagem de negócio.
"""

from __future__ import annotations

import math
import re
from typing import Any

from app.core.errors import DomainError
from app.modules.idp.types import IDP_SCORECARD_POINTS, IDP_SCORECARD_WEIGHT, IdpResult
from app.shared.dates import to_iso_date_key

__all__ = ["round_percent", "to_idp_published_payload"]

_INPASA_PREFIX_RE = re.compile(r"^INPASA\s*", re.IGNORECASE)


def _round_half_up(value: float, decimals: int = 0) -> float:
    factor = 10**decimals
    return math.floor(value * factor + 0.5) / factor


def round_percent(value: float) -> float:
    """Fração -> percentual com 2 casas decimais (`Math.round(v*10000)/100`)."""
    return _round_half_up(value * 100, 2)


def to_idp_published_payload(result: IdpResult, target_percent: float) -> dict[str, Any]:
    if result.active_documents == 0 or result.total_previsto_medio <= 0:
        raise DomainError(
            "Não há RSO com execução prevista válida na competência selecionada para publicar."
        )
    if result.aderencia_geral is None:
        # Inalcançável na prática: total_previsto_medio > 0 implica pelo menos
        # uma unidade incluída com aderência não-nula. Guarda defensiva.
        raise DomainError(
            "Não há RSO com execução prevista válida na competência selecionada para publicar."
        )

    resultado = round_percent(result.aderencia_geral)

    def _discipline_value(name: str) -> float | None:
        row = next((r for r in result.discipline_rows if r.disciplina == name), None)
        if row is None or row.aderencia is None:
            return None
        return round_percent(row.aderencia)

    unidades = [
        {
            "n": _INPASA_PREFIX_RE.sub("", u.unit).strip(),
            "v": round_percent(u.aderencia) if u.aderencia is not None else None,
            "rsoNumero": u.rso_numero,
            "referenceYear": u.reference_year,
            "referenceMonth": u.reference_month,
            "referenceSource": u.reference_source,
            "referenceOriginalText": u.reference_original_text,
            "referenceAdjusted": u.reference_adjusted,
            "periodStart": to_iso_date_key(u.period_start) if u.period_start else None,
            "periodEnd": to_iso_date_key(u.period_end) if u.period_end else None,
            "emissionDate": to_iso_date_key(u.emission_date) if u.emission_date else None,
            "fileName": u.file_name,
        }
        for u in result.unit_rows
        if not u.excluded
    ]

    disciplinas = [
        {"n": r.disciplina, "v": round_percent(r.aderencia) if r.aderencia is not None else None}
        for r in result.discipline_rows
    ]

    mensal = [
        {
            "label": m.label,
            "v": round_percent(m.aderencia) if m.aderencia is not None else None,
            "linhaBase": m.total_previsto_medio,
            "real": m.total_real_medio,
            "documentosAtivos": m.active_documents,
        }
        for m in result.monthly
    ]

    return {
        "pontos": IDP_SCORECARD_POINTS,
        "peso": IDP_SCORECARD_WEIGHT,
        "meta": target_percent,
        "resultado": resultado,
        "civil": _discipline_value("01 - Civil"),
        "mecanica": _discipline_value("02 - Mecânica"),
        "eletrica": _discipline_value("04 - Elétrica"),
        "selectedYear": result.selected_year,
        "selectedMonth": result.selected_month,
        "historyStartYear": result.history_start_year,
        "historyMonthStart": result.history_month_start,
        "historyEndYear": result.history_end_year,
        "historyMonthEnd": result.history_month_end,
        "periodo": {
            "startYear": result.history_start_year,
            "startMonth": result.history_month_start,
            "endYear": result.history_end_year,
            "endMonth": result.history_month_end,
        },
        "monthStart": result.history_month_start,
        "monthEnd": result.history_month_end,
        "totalLinhaBase": result.total_previsto_medio,
        "totalReal": result.total_real_medio,
        "documentosAtivos": result.active_documents,
        "unidades": unidades,
        "disciplinas": disciplinas,
        "mensal": mensal,
    }
