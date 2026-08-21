"""Cadastro canônico das unidades operacionais. Porte literal de `src/lib/units.ts`.

Compartilhado por todos os módulos (RDO, RNC, 5S, IDP, Taxa de Acidentes).
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
    UnitDefinition("RDN", "RONDONOPOLIS"),
    UnitDefinition("SDR", "SIDROLANDIA"),
)

_UNIT_BY_CODE = {u.code: u for u in UNITS}
_UNIT_ORDER = {u.code: i for i, u in enumerate(UNITS)}


def normalize_unit_code(value: object) -> str:
    """Converte sigla, nome completo (qualquer caixa/acentuação) ou rótulo
    combinado para a sigla oficial. Unidades fora do cadastro continuam
    disponíveis, estabilizadas em caixa alta."""
    raw = collapse_spaces(str(value) if value is not None else "")
    if not raw:
        return ""

    normalized = normalize_for_match(raw)
    tokens = normalized.split(" ")

    for unit in UNITS:
        normalized_name = normalize_for_match(unit.name)
        if (
            normalized == unit.code
            or normalized == normalized_name
            or normalized == f"{unit.code} {normalized_name}"
            or normalized == f"{normalized_name} {unit.code}"
            or unit.code in tokens
            or normalized_name in normalized
        ):
            return unit.code

    return raw.upper()


def format_unit_label(value: object) -> str:
    """Exibe o nome completo por extenso da unidade — nunca a sigla."""
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
