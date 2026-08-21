"""Parsing e formatação de datas. Porte literal de `src/lib/dates/index.ts`."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

MONTH_NAMES = [
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
]

MONTH_NAMES_FULL = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

_EXCEL_EPOCH = datetime(1899, 12, 30)

_BR_DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})")
_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})")


def excel_serial_to_date(serial: float) -> datetime | None:
    """Serial do Excel (epoch 30/12/1899) para datetime."""
    try:
        return _EXCEL_EPOCH + timedelta(days=serial)
    except (OverflowError, ValueError, TypeError):
        return None


def parse_flex_date(value: object) -> datetime | None:
    """Aceita datetime/date, serial do Excel (número) ou string em
    DD/MM/YYYY, YYYY-MM-DD ou formato livre. Retorna None se não parseável."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, int | float) and not isinstance(value, bool):
        return excel_serial_to_date(value)
    if isinstance(value, str):
        text = value.strip()
        m = _BR_DATE_RE.match(text)
        if m:
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                return datetime(year, month, day)
            except ValueError:
                return None
        m = _ISO_DATE_RE.match(text)
        if m:
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                return datetime(year, month, day)
            except ValueError:
                return None
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


def to_iso_date_key(value: object) -> str:
    """Data em ISO (YYYY-MM-DD) usada para chaves. Retorna "" se inválida."""
    parsed = parse_flex_date(value)
    if parsed is None:
        return ""
    return parsed.strftime("%Y-%m-%d")


def fmt_date_br(value: datetime | date | None) -> str:
    if value is None:
        return "—"
    return f"{value.day:02d}/{value.month:02d}/{value.year}"


def month_index_pt(name: object) -> int:
    """Índice do mês (1..12) a partir do nome em português (completo ou
    abreviado) ou número textual. Retorna 0 se não reconhecer."""
    text = str(name).strip().lower() if name is not None else ""
    if not text:
        return 0
    for i, full in enumerate(MONTH_NAMES_FULL):
        if full.lower() == text:
            return i + 1
    for i, abbr in enumerate(MONTH_NAMES):
        if abbr.lower() == text:
            return i + 1
    try:
        num = int(text)
        if 1 <= num <= 12:
            return num
    except ValueError:
        pass
    return 0
