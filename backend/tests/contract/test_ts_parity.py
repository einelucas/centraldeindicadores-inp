"""Testes de contrato — paridade entre TypeScript (`src/lib/**`) e Python
(`app/shared/**`) para as mesmas entradas.

Os vetores em `tests/fixtures/contract_vectors.json` foram gerados
executando o código TypeScript REAL (não uma reimplementação em JS) via
`npx tsx scripts/generate-contract-vectors.ts` na raiz do repositório —
ver esse arquivo para regenerar após qualquer mudança em `src/lib/**`.

Não depende de banco de dados nem de nenhum módulo de indicador — cobre só
as funções compartilhadas (hashing, normalização, datas, período), que já
estão implementadas e estáveis.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.shared.dates import excel_serial_to_date, fmt_date_br, parse_flex_date, to_iso_date_key
from app.shared.hashing import build_key_string, make_business_key, make_content_hash, sha256
from app.shared.normalization import (
    collapse_spaces,
    norm_header,
    normalize_for_key,
    normalize_for_match,
    null_if_empty,
)
from app.shared.period import (
    PeriodRange,
    Semester,
    cycle_for_month,
    cycle_from_year_semester,
    format_period_range_label,
    get_operational_period,
    is_within_period_range,
    normalize_period_range,
)

FIXTURES = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "contract_vectors.json").read_text(
        encoding="utf-8"
    )
)


def test_business_key_matches_typescript() -> None:
    for case in FIXTURES["businessKey"]:
        parts = [None if p is None else p for p in case["input"]["parts"]]
        result = make_business_key(case["input"]["module"], parts)
        assert result == case["output"], case


def test_build_key_string_matches_typescript() -> None:
    for case in FIXTURES["buildKeyString"]:
        assert build_key_string(case["input"]) == case["output"]


def test_sha256_matches_typescript() -> None:
    for case in FIXTURES["sha256"]:
        assert sha256(case["input"]) == case["output"]


def test_content_hash_matches_typescript() -> None:
    for case in FIXTURES["contentHash"]:
        assert make_content_hash(case["input"]) == case["output"]


def test_normalize_for_key_matches_typescript() -> None:
    for case in FIXTURES["normalizeForKey"]:
        assert normalize_for_key(case["input"]) == case["output"]


def test_normalize_for_match_matches_typescript() -> None:
    for case in FIXTURES["normalizeForMatch"]:
        assert normalize_for_match(case["input"]) == case["output"]


def test_collapse_spaces_matches_typescript() -> None:
    for case in FIXTURES["collapseSpaces"]:
        assert collapse_spaces(case["input"]) == case["output"]


def test_norm_header_matches_typescript() -> None:
    for case in FIXTURES["normHeader"]:
        assert norm_header(case["input"]) == case["output"]


def test_null_if_empty_matches_typescript() -> None:
    for case in FIXTURES["nullIfEmpty"]:
        assert null_if_empty(case["input"]) == case["output"]


def test_to_iso_date_key_matches_typescript() -> None:
    for case in FIXTURES["toIsoDateKey"]:
        assert to_iso_date_key(case["input"]) == case["output"]


def test_parse_flex_date_matches_typescript() -> None:
    for case in FIXTURES["parseFlexDateValid"]:
        parsed = parse_flex_date(case["input"])
        assert parsed is not None, case
        assert (parsed.year, parsed.month, parsed.day) == (
            case["output"]["y"],
            case["output"]["m"],
            case["output"]["d"],
        ), case


def test_excel_serial_to_date_matches_typescript() -> None:
    for case in FIXTURES["excelSerialToDate"]:
        parsed = excel_serial_to_date(case["input"])
        assert parsed is not None
        assert (parsed.year, parsed.month, parsed.day) == (
            case["output"]["y"],
            case["output"]["m"],
            case["output"]["d"],
        ), case


def test_fmt_date_br_matches_typescript() -> None:
    for case in FIXTURES["fmtDateBR"]:
        parsed = parse_flex_date(case["input"])
        assert fmt_date_br(parsed) == case["output"], case


def test_get_operational_period_matches_typescript() -> None:
    for case in FIXTURES["getOperationalPeriod"]:
        result = get_operational_period(case["input"]["year"], case["input"]["month"])
        assert result.period_year == case["output"]["periodYear"], case
        assert result.semester.value == case["output"]["semester"], case


def test_cycle_from_year_semester_matches_typescript() -> None:
    for case in FIXTURES["cycleFromYearSemester"]:
        semester = Semester.S1 if case["input"]["semester"] == "S1" else Semester.S2
        result = cycle_from_year_semester(case["input"]["year"], semester)
        assert result.start_year == case["output"]["startYear"]
        assert result.start_month == case["output"]["startMonth"]
        assert result.end_year == case["output"]["endYear"]
        assert result.end_month == case["output"]["endMonth"]


def test_cycle_for_month_matches_typescript() -> None:
    for case in FIXTURES["cycleForMonth"]:
        result = cycle_for_month(case["input"]["year"], case["input"]["month"])
        assert result.start_year == case["output"]["startYear"]
        assert result.start_month == case["output"]["startMonth"]
        assert result.end_year == case["output"]["endYear"]
        assert result.end_month == case["output"]["endMonth"]


def test_normalize_period_range_matches_typescript() -> None:
    for case in FIXTURES["normalizePeriodRange"]:
        pr = PeriodRange(
            start_year=case["input"]["startYear"],
            start_month=case["input"]["startMonth"],
            end_year=case["input"]["endYear"],
            end_month=case["input"]["endMonth"],
        )
        result = normalize_period_range(pr)
        assert result.start_year == case["output"]["startYear"]
        assert result.start_month == case["output"]["startMonth"]
        assert result.end_year == case["output"]["endYear"]
        assert result.end_month == case["output"]["endMonth"]


def test_is_within_period_range_matches_typescript() -> None:
    for case in FIXTURES["isWithinPeriodRange"]:
        r = case["input"]["range"]
        pr = PeriodRange(
            start_year=r["startYear"], start_month=r["startMonth"],
            end_year=r["endYear"], end_month=r["endMonth"],
        )
        result = is_within_period_range(case["input"]["year"], case["input"]["month"], pr)
        assert result == case["output"], case


def test_format_period_range_label_matches_typescript() -> None:
    for case in FIXTURES["formatPeriodRangeLabel"]:
        if case["input"] is None:
            pr = None
        else:
            r = case["input"]
            pr = PeriodRange(
                start_year=r["startYear"],
                start_month=r["startMonth"],
                end_year=r["endYear"],
                end_month=r["endMonth"],
            )
        assert format_period_range_label(pr) == case["output"], case
