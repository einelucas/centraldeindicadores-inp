"""Formatação de números no padrão pt-BR, compartilhada pelos 5 geradores de
sugestão de justificativa (`app/modules/justifications/generators/*.py`).
Porte do padrão `toLocaleString("pt-BR", { maximumFractionDigits: N })`
repetido em cada gerador TS original."""

from __future__ import annotations


def format_pt_br(value: float, max_decimals: int = 1) -> str:
    """Formata um número no padrão pt-BR (`,` decimal, `.` milhar), com no
    máximo `max_decimals` casas decimais e sem zeros à direita — equivalente
    a `toLocaleString("pt-BR", { maximumFractionDigits: max_decimals })`."""
    rounded = round(value, max_decimals)
    if rounded == 0:
        rounded = 0.0  # evita "-0"
    formatted = f"{rounded:,.{max_decimals}f}" if max_decimals > 0 else f"{rounded:,.0f}"
    # troca separadores: "1,234.5" (US) -> "1.234,5" (pt-BR)
    formatted = formatted.replace(",", "§").replace(".", ",").replace("§", ".")
    if max_decimals > 0 and "," in formatted:
        integer_part, _, decimal_part = formatted.partition(",")
        decimal_part = decimal_part.rstrip("0")
        formatted = integer_part if not decimal_part else f"{integer_part},{decimal_part}"
    return formatted
