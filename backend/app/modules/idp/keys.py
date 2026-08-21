"""Business key e content hash do IDP/RSO. Porte de
`src/features/idp/utils/keys.ts`.

**Nota de paridade** (documentada em `docs/backend-migration-decisions.md`
§4.2.3): os campos `areas`/`discData`/`execucaoFases` são estruturas
aninhadas (lista/objeto), não escalares. O inventário de origem não deixou
claro como `makeContentHash` (que documentadamente faz `String(value)` sobre
cada campo) serializa um array/objeto sem quebrar a sensibilidade do hash a
mudanças de conteúdo — diferente do 5S, que documenta explicitamente um
pré-processamento (`join` de strings ordenadas) antes de chamar
`makeContentHash`. Aqui, cada uma dessas três estruturas é serializada via
`json.dumps(..., sort_keys=True)` antes de entrar no hash — garante
determinismo e sensibilidade real a mudanças de conteúdo (a propriedade que
importa para a idempotência do motor incremental), mesmo que o valor exato
do hash não seja garantidamente idêntico a uma eventual peculiaridade do TS
original que não pôde ser verificada a partir do inventário disponível.
"""

from __future__ import annotations

import json

from app.modules.idp.calculations import normalized_unit_key
from app.modules.idp.types import IdpAreaEntry, IdpExecutionPhase, IdpNormalizedRecord
from app.shared.dates import to_iso_date_key
from app.shared.hashing import make_business_key, make_content_hash

__all__ = ["idp_business_key", "idp_content_hash"]


def _serialize_disc_data(disc_data: dict[str, list[IdpAreaEntry]]) -> str:
    plain = {
        disciplina: [{"area": e.area, "prevAcum": e.prev_acum, "realAcum": e.real_acum} for e in entries]
        for disciplina, entries in disc_data.items()
    }
    return json.dumps(plain, sort_keys=True, ensure_ascii=False)


def _serialize_execution_phases(phases: list[IdpExecutionPhase]) -> str:
    plain = [{"label": p.label, "prevAcum": p.prev_acum, "realAcum": p.real_acum} for p in phases]
    return json.dumps(plain, sort_keys=True, ensure_ascii=False)


def idp_business_key(record: IdpNormalizedRecord) -> str:
    """Identidade lógica: unidade normalizada (leve, `normalized_unit_key` —
    NÃO o código canônico) + número do RSO."""
    return make_business_key("IDP_RSO", [normalized_unit_key(record.unit), str(record.rso_numero)])


def idp_content_hash(record: IdpNormalizedRecord) -> str:
    """Campos mutáveis: unidade, número do RSO, competência (ano/mês/fonte/
    ajustada), período/emissão, e os três blobs de dados. `unitAdjusted`,
    `rsoAdjusted`, `detected*`, `referenceOriginalText`, `raw`, `fileName`
    NÃO entram no hash — mudar só esses campos não dispara `update`."""
    return make_content_hash(
        {
            "unit": record.unit,
            "rsoNumero": record.rso_numero,
            "referenceYear": record.reference_year,
            "referenceMonth": record.reference_month,
            "referenceSource": record.reference_source,
            "referenceAdjusted": record.reference_adjusted,
            "periodStart": to_iso_date_key(record.period_start) if record.period_start else "",
            "periodEnd": to_iso_date_key(record.period_end) if record.period_end else "",
            "emissionDate": to_iso_date_key(record.emission_date) if record.emission_date else "",
            "areas": ",".join(record.areas),
            "discData": _serialize_disc_data(record.disc_data),
            "execucaoFases": _serialize_execution_phases(record.execucao_fases),
        }
    )
