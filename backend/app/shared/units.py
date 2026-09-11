"""Cadastro canônico das unidades operacionais.

Compartilhado por todos os módulos (RDO, RNC, 5S, IDP). Uma mesma unidade
pode aparecer nos arquivos de origem sob mais de uma sigla — por isso
`UNIT_CODE_ALIASES` resolve siglas alternativas para o código canônico antes
de qualquer agregação/exibição, garantindo que a unidade seja sempre
consolidada sob um único nome. Siglas não cadastradas aqui NUNCA são
inventadas — permanecem como texto livre, estabilizado em caixa alta.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.shared.normalization import collapse_spaces, normalize_for_match


@dataclass(frozen=True, slots=True)
class UnitDefinition:
    code: str
    name: str


UNITS: tuple[UnitDefinition, ...] = (
    UnitDefinition("LEM", "LUIS EDUARDO MAGALHÃES"),
    UnitDefinition("MTU", "NOVA MUTUM"),
    UnitDefinition("RVD", "RIO VERDE"),
    UnitDefinition("BLS", "BALSAS"),
    UnitDefinition("SNP", "SINOP"),
    UnitDefinition("DRD", "DOURADOS"),
    UnitDefinition("RDN", "RONDONÓPOLIS"),
    UnitDefinition("SDL", "SIDROLÂNDIA"),
    UnitDefinition("LRL", "LAUREL"),
)

# Siglas alternativas encontradas nos arquivos de origem que representam a
# MESMA unidade que um código já cadastrado acima — nunca criam uma unidade
# nova, só resolvem para o código canônico (ex.: NMT e MTU são a mesma
# unidade, NOVA MUTUM, e devem ser consolidadas sob um único nome em todos
# os filtros, gráficos e totalizações).
UNIT_CODE_ALIASES: dict[str, str] = {
    "NMT": "MTU",
    # "SDR" era o código usado para esta unidade antes da correção para o
    # código oficial "SDL" — mantido como alias para não deixar de reconhecer
    # arquivos de origem antigos que ainda usem a sigla anterior.
    "SDR": "SDL",
}

_UNIT_BY_CODE = {u.code: u for u in UNITS}
_UNIT_ORDER = {u.code: i for i, u in enumerate(UNITS)}
_CODE_LOOKUP: dict[str, str] = {**{u.code: u.code for u in UNITS}, **UNIT_CODE_ALIASES}


def normalize_unit_code(value: object) -> str:
    """Converte sigla (inclusive alias), nome completo (qualquer
    caixa/acentuação) ou rótulo combinado para a sigla oficial. Unidades fora
    do cadastro continuam disponíveis, estabilizadas em caixa alta — nunca
    são presumidas como uma unidade cadastrada."""
    raw = collapse_spaces(str(value) if value is not None else "")
    if not raw:
        return ""

    normalized = normalize_for_match(raw)

    if normalized in _CODE_LOOKUP:
        return _CODE_LOOKUP[normalized]

    for unit in UNITS:
        normalized_name = normalize_for_match(unit.name)
        if (
            normalized == normalized_name
            or normalized == f"{unit.code} {normalized_name}"
            or normalized == f"{normalized_name} {unit.code}"
            or normalized_name in normalized
        ):
            return unit.code

    for token in normalized.split(" "):
        if token in _CODE_LOOKUP:
            return _CODE_LOOKUP[token]

    return raw.upper()


def format_unit_label(value: object) -> str:
    """Exibe o nome completo por extenso da unidade — nunca a sigla nem
    prefixos soltos. Este é o único texto que deve chegar à interface."""
    code = normalize_unit_code(value)
    unit = _UNIT_BY_CODE.get(code)
    return unit.name if unit else code


def compare_units(a: object, b: object) -> int:
    """Mantém as unidades oficiais na ordem operacional cadastrada."""
    code_a = normalize_unit_code(a)
    code_b = normalize_unit_code(b)
    order_a = _UNIT_ORDER.get(code_a, len(UNITS) + 1)
    order_b = _UNIT_ORDER.get(code_b, len(UNITS) + 1)
    if order_a != order_b:
        return order_a - order_b
    label_a, label_b = format_unit_label(code_a), format_unit_label(code_b)
    return -1 if label_a < label_b else (1 if label_a > label_b else 0)
