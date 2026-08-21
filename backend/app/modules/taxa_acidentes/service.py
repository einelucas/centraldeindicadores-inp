"""Orquestração de negócio — Taxa de Acidentes.

Porte de `src/features/taxa-acidentes/services/index.ts` e da lógica contida
nos handlers de `src/app/api/taxa-acidentes/**` (que no Next.js ficava
diretamente na rota; aqui vive nesta camada de serviço para manter
`router.py` fino).

Módulo 100% administrativo/manual — não há `recalc_indicators` acionado por
importação de planilha. `recalc_accident_rate_indicators` só é chamado a
partir do fluxo de PUBLICAÇÃO (`POST /publicacoes/taxa-acidentes`), exatamente
como `saveAccidentIndicatorResult` só era chamado ali no TypeScript — o
cadastro manual (`POST /taxa-acidentes`) nunca recalcula `IndicatorResult`.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, DomainError, NotFoundError
from app.models.indicators import IndicatorResult
from app.models.records import AccidentMonthlyRecord, AccidentUnitRecord
from app.modules.taxa_acidentes import repository
from app.modules.taxa_acidentes.calculations import compute_accident_rate_result, sort_unit_inputs
from app.modules.taxa_acidentes.types import (
    ACCIDENT_EXCLUDED_SETTING_KEY,
    ACCIDENT_RATE_TARGET,
    ACCIDENT_TARGET_SETTING_KEY,
    INDICATOR,
    MODULE,
    AccidentMonthlyInput,
    AccidentRateResult,
    AccidentUnitInput,
)
from app.shared.normalization import normalize_for_match
from app.shared.period import PeriodRange
from app.shared.units import normalize_unit_code


def accident_unit_key(unit: str) -> str:
    """Chave estável de deduplicação/matching — `accidentUnitKey` no TS."""
    return normalize_for_match(normalize_unit_code(unit))


def normalize_excluded_units(values: list[str]) -> list[str]:
    """Normaliza cada código via `normalize_unit_code`, remove vazios, deduplica
    preservando a primeira ocorrência (equivalente a `Array.from(new Set(...))`)."""
    normalized: list[str] = []
    for value in values:
        code = normalize_unit_code(value)
        if code and code not in normalized:
            normalized.append(code)
    return normalized


# --- Configurações (meta / unidades ignoradas) ---------------------------------


async def load_accident_target(session: AsyncSession) -> float:
    setting = await repository.get_setting(session, ACCIDENT_TARGET_SETTING_KEY)
    if setting is None:
        return ACCIDENT_RATE_TARGET
    try:
        configured = float(setting.value)
    except (TypeError, ValueError):
        return ACCIDENT_RATE_TARGET
    if configured >= 0:
        return configured
    return ACCIDENT_RATE_TARGET


async def save_accident_target(session: AsyncSession, target: float) -> None:
    await repository.upsert_setting(session, ACCIDENT_TARGET_SETTING_KEY, target)


async def load_accident_excluded_units(session: AsyncSession) -> list[str]:
    setting = await repository.get_setting(session, ACCIDENT_EXCLUDED_SETTING_KEY)
    if setting is None or not isinstance(setting.value, list):
        return []
    return normalize_excluded_units([str(value) for value in setting.value])


async def save_accident_excluded_units(session: AsyncSession, excluded_units: list[str]) -> list[str]:
    normalized = normalize_excluded_units(excluded_units)
    await repository.upsert_setting(session, ACCIDENT_EXCLUDED_SETTING_KEY, normalized)
    return normalized


# --- Leitura consolidada (GET /taxa-acidentes e POST /publicacoes/taxa-acidentes) -


@dataclass(frozen=True, slots=True)
class AccidentRateData:
    monthly: list[AccidentMonthlyInput]
    units: list[AccidentUnitInput]
    target: float
    excluded_units: list[str]
    result: AccidentRateResult


async def load_accident_rate_data(
    session: AsyncSession, period: PeriodRange | None = None
) -> AccidentRateData:
    """Porte de `loadAccidentRateData`.

    ⚠️ Peculiaridade preservada de propósito: `monthly`/`units` retornados
    aqui carregam TODAS as linhas das duas tabelas, sem filtro de período —
    só `result` (calculado por `compute_accident_rate_result`) respeita
    `period`. Ver inventário, rota GET /taxa-acidentes.
    """
    monthly_rows = await repository.list_all_monthly(session)
    unit_rows = await repository.list_all_units(session)
    target = await load_accident_target(session)
    excluded_units = await load_accident_excluded_units(session)

    monthly = [
        AccidentMonthlyInput(id=row.id, year=row.year, month=row.month, rate=row.rate, caf=row.caf)
        for row in monthly_rows
    ]
    units_raw = [
        AccidentUnitInput(
            id=row.id,
            year=row.year,
            month=row.month,
            unit=normalize_unit_code(row.unit or row.unitKey),
            unit_key=accident_unit_key(row.unit or row.unitKey),
            saf=row.saf,
            caf=row.caf,
        )
        for row in unit_rows
    ]
    units = sort_unit_inputs(units_raw)

    result = compute_accident_rate_result(monthly, units, target, excluded_units, period)
    return AccidentRateData(
        monthly=monthly, units=units, target=target, excluded_units=excluded_units, result=result
    )


async def recalc_accident_rate_indicators(session: AsyncSession, result: AccidentRateResult) -> None:
    """Upsert em `IndicatorResult` (`module="taxa-acidentes"`, `unit="__ALL__"`,
    ano/mês = competência mais recente do período publicado). Porte de
    `saveAccidentIndicatorResult`. Só é chamado pelo fluxo de publicação."""
    if result.result is None or result.latest_year is None or result.latest_month is None:
        return

    adherence = result.target / result.result if result.result > 0 else 1
    status = "OK" if result.result <= result.target else "ACIMA"
    details = {
        "totalCaf": result.total_caf,
        "totalUnitCaf": result.total_unit_caf,
        "totalSaf": result.total_saf,
        "latestRate": result.latest_rate,
        "monthsCount": result.months_count,
    }

    existing = await repository.get_indicator_result(
        session,
        module=MODULE,
        indicator=INDICATOR,
        unit="__ALL__",
        year=result.latest_year,
        month=result.latest_month,
    )
    if existing is None:
        session.add(
            IndicatorResult(
                module=MODULE,
                indicator=INDICATOR,
                unit="__ALL__",
                year=result.latest_year,
                month=result.latest_month,
                value=result.result,
                target=result.target,
                adherence=adherence,
                status=status,
                details=details,
            )
        )
    else:
        existing.value = result.result
        existing.target = result.target
        existing.adherence = adherence
        existing.status = status
        existing.details = details
    await session.flush()


# --- Cadastro/edição manual (POST /taxa-acidentes) ------------------------------


def _monthly_snapshot(record: AccidentMonthlyRecord) -> dict:
    return {
        "id": record.id, "year": record.year, "month": record.month,
        "rate": record.rate, "caf": record.caf,
    }


def _unit_snapshot(record: AccidentUnitRecord) -> dict:
    return {
        "id": record.id,
        "year": record.year,
        "month": record.month,
        "unit": record.unit,
        "unitKey": record.unitKey,
        "saf": record.saf,
        "caf": record.caf,
    }


@dataclass(frozen=True, slots=True)
class MonthlySaveOutcome:
    saved: AccidentMonthlyRecord
    previous: dict | None
    created: bool


async def upsert_monthly_entry(
    session: AsyncSession, *, id: str | None, year: int, month: int, rate: float, caf: int
) -> MonthlySaveOutcome:
    """Porte do ramo `type: "month"` de `POST /api/taxa-acidentes`."""
    previous = (
        await repository.get_monthly_by_id(session, id)
        if id
        else await repository.get_monthly_by_year_month(session, year, month)
    )
    if id and previous is None:
        raise NotFoundError("O lançamento mensal selecionado não foi encontrado.")

    conflict = await repository.get_monthly_by_year_month(session, year, month)
    if conflict is not None and (previous is None or conflict.id != previous.id):
        raise ConflictError("Já existe um lançamento mensal para essa competência.")

    previous_snapshot = _monthly_snapshot(previous) if previous is not None else None

    if previous is not None:
        previous.year = year
        previous.month = month
        previous.rate = rate
        previous.caf = caf
        saved = previous
        created = False
    else:
        saved = AccidentMonthlyRecord(year=year, month=month, rate=rate, caf=caf)
        session.add(saved)
        created = True

    await session.flush()
    return MonthlySaveOutcome(saved=saved, previous=previous_snapshot, created=created)


@dataclass(frozen=True, slots=True)
class UnitSaveOutcome:
    saved: AccidentUnitRecord
    previous: dict | None
    created: bool


async def upsert_unit_entry(
    session: AsyncSession, *, id: str | None, year: int, month: int, unit: str, saf: int, caf: int
) -> UnitSaveOutcome:
    """Porte do ramo `type: "unit"` de `POST /api/taxa-acidentes` — inclusive o
    upsert silencioso por chave de negócio (`year+month+unitKey`) quando não
    há `id` mas já existe um lançamento equivalente para a mesma competência."""
    normalized_unit = normalize_unit_code(unit)
    unit_key = accident_unit_key(normalized_unit)
    if not unit_key:
        raise DomainError("Informe uma unidade válida.")

    previous_by_id = await repository.get_unit_by_id(session, id) if id else None
    if id and previous_by_id is None:
        raise NotFoundError("O lançamento da unidade selecionada não foi encontrado.")

    target_period_rows = await repository.list_units_for_period(session, year, month)
    equivalent_rows = [
        row
        for row in target_period_rows
        if row.id != id and accident_unit_key(row.unit or row.unitKey) == unit_key
    ]
    equivalent_row = next((row for row in equivalent_rows if row.unitKey == unit_key), None)
    if equivalent_row is None and equivalent_rows:
        equivalent_row = equivalent_rows[0]

    if id and equivalent_row is not None:
        raise ConflictError("Já existe um lançamento dessa unidade para a competência selecionada.")

    previous = previous_by_id or equivalent_row
    previous_snapshot = _unit_snapshot(previous) if previous is not None else None

    if previous is not None:
        previous.year = year
        previous.month = month
        previous.unit = normalized_unit
        previous.unitKey = unit_key
        previous.saf = saf
        previous.caf = caf
        saved = previous
        created = False
    else:
        saved = AccidentUnitRecord(
            year=year, month=month, unit=normalized_unit, unitKey=unit_key, saf=saf, caf=caf
        )
        session.add(saved)
        created = True

    await session.flush()
    return UnitSaveOutcome(saved=saved, previous=previous_snapshot, created=created)


# --- Exclusão de um único registro (DELETE /taxa-acidentes?kind=month|unit) -----


async def delete_monthly_entry(
    session: AsyncSession, *, year: int, month: int
) -> AccidentMonthlyRecord | None:
    """`kind=month` — endereça por `year`+`month` (não por `id`). Idempotente:
    retorna `None` silenciosamente se não encontrado (sem 404)."""
    previous = await repository.get_monthly_by_year_month(session, year, month)
    if previous is not None:
        await session.delete(previous)
        await session.flush()
    return previous


async def delete_unit_entry(session: AsyncSession, *, record_id: str) -> AccidentUnitRecord | None:
    """`kind=unit` — endereça por `id` (não por `year`+`month`+`unit`)."""
    previous = await repository.get_unit_by_id(session, record_id)
    if previous is not None:
        await session.delete(previous)
        await session.flush()
    return previous


# --- Exclusão em massa (DELETE /taxa-acidentes/registros) -----------------------


@dataclass(frozen=True, slots=True)
class RecordCounts:
    monthly_count: int
    unit_count: int

    @property
    def total(self) -> int:
        return self.monthly_count + self.unit_count


async def count_records(session: AsyncSession, period: PeriodRange | None) -> RecordCounts:
    monthly_count = await repository.count_monthly(session, period)
    unit_count = await repository.count_units(session, period)
    return RecordCounts(monthly_count=monthly_count, unit_count=unit_count)


async def clear_all_records(session: AsyncSession) -> RecordCounts:
    """Ramo `{all: true}` — apaga as duas tabelas E os `IndicatorResult` do
    módulo. Sem transação/auditoria se já estiver tudo vazio (paridade com
    o TS: `if (monthlyCount + unitCount === 0) return ...`)."""
    counts = await count_records(session, None)
    if counts.total == 0:
        return counts
    await repository.delete_all_monthly(session)
    await repository.delete_all_units(session)
    await repository.delete_indicator_results_for_module(session, MODULE)
    return counts


async def clear_records_in_period(session: AsyncSession, period: PeriodRange) -> RecordCounts:
    """Ramo com período — apaga só o intervalo informado. `IndicatorResult`
    NÃO é apagado aqui (assimetria preservada do TS)."""
    counts = await count_records(session, period)
    if counts.total == 0:
        return counts
    await repository.delete_monthly_in_period(session, period)
    await repository.delete_units_in_period(session, period)
    return counts
