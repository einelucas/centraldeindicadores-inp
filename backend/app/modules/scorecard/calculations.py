"""Cálculos puros do Scorecard 2026 e do Painel Geral (consolidado).

Porte de `src/features/scorecard/calculations/index.ts` e
`src/features/scorecard/publications/index.ts`, mais duas peças que no
código-fonte original vivem só no frontend / não existem:

- `merge_live_with_saved_fallback` — porte de `effectiveByPeriod`
  (`ScorecardView.tsx`, linhas ~296-378): o valor ao vivo (publicação
  vigente) sempre vence um `ScorecardSnapshot` salvo; o snapshot só entra
  como respaldo quando não existe valor ao vivo para aquele indicador/mês.
  Isso vivia apenas no cliente React — aqui vira uma função de serviço do
  backend, usada tanto pelo Scorecard quanto pelo Painel Geral.
- `compute_general_panel` — consolida em UMA função o que no TS são duas
  camadas encadeadas (`buildGeneralPanelData` + `applySpreadsheetScore`,
  ver `src/app/api/dashboard/route.ts`). A camada base (`buildGeneralPanelData`)
  isolada arredonda `pontosRealizados` com `Math.round`, mas a rota HTTP
  real sempre aplica `applySpreadsheetScore` por cima, que recalcula tudo
  SEM arredondamento — esse é o comportamento observável da API. Aqui só
  existe o caminho sem arredondamento intermediário (arredondamento é
  responsabilidade exclusiva da apresentação, nunca do backend).

Todas as funções aqui são puras (sem I/O) — recebem publicações/valores já
carregados do banco e devolvem estruturas de dados. `service.py` cuida da
parte de banco e monta os argumentos para estas funções.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, TypeGuard, runtime_checkable

from app.modules.scorecard.types import (
    SC_INDICATORS,
    SCORECARD_MAX_POINTS,
    SCORECARD_MONTHLY_POOL,
    SHORT_LABELS,
    ScorecardIndicator,
)
from app.shared.period import MONTH_NAMES, MONTH_NAMES_FULL, PeriodRange, enumerate_period_months

# ---------------------------------------------------------------------------
# Camada 1 — computeScorecard (uma competência/mês), usado por /scorecard.
# ---------------------------------------------------------------------------


def _is_finite_number(value: Any) -> TypeGuard[float]:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def indicator_monthly_points(indicator: ScorecardIndicator) -> float:
    """Pontos mensais disponíveis para um indicador conforme seu peso."""
    return (indicator.peso / 100) * SCORECARD_MONTHLY_POOL


@dataclass(slots=True)
class ScoredValue:
    passed: bool
    pontos: float
    pontos_possiveis: float
    has_value: bool


def score_indicator(indicator: ScorecardIndicator, value: float | None) -> ScoredValue:
    """Avalia um indicador e aplica a regra binária da planilha (sem
    tolerância nem pontuação parcial — meta exata já passa)."""
    pontos_possiveis = indicator_monthly_points(indicator)

    if not _is_finite_number(value):
        return ScoredValue(passed=False, pontos=0.0, pontos_possiveis=pontos_possiveis, has_value=False)

    assert value is not None  # narrowed by _is_finite_number
    passed = value >= indicator.meta if indicator.direction == "higher" else value <= indicator.meta
    return ScoredValue(
        passed=passed,
        pontos=pontos_possiveis if passed else 0.0,
        pontos_possiveis=pontos_possiveis,
        has_value=True,
    )


@dataclass(slots=True)
class ScorecardRow:
    key: str
    label: str
    peso: float
    meta: float
    direction: str
    unit: str
    value: float | None
    passed: bool
    pontos: float
    pontos_possiveis: float
    has_value: bool


@dataclass(slots=True)
class ScorecardResult:
    rows: list[ScorecardRow]
    total_pontos: float
    total_peso: float
    pontos_possiveis_mes: float
    atendimento_mes: float


def compute_scorecard(
    values: Mapping[str, float | None],
    indicators: Sequence[ScorecardIndicator] = SC_INDICATORS,
) -> ScorecardResult:
    """Consolida os cinco indicadores para um mês. Sem `round` em nenhum
    ponto — precisão decimal total, o arredondamento é só de apresentação."""
    rows: list[ScorecardRow] = []
    for indicator in indicators:
        raw_value = values.get(indicator.key)
        scored = score_indicator(indicator, raw_value)
        rows.append(
            ScorecardRow(
                key=indicator.key,
                label=indicator.label,
                peso=indicator.peso,
                meta=indicator.meta,
                direction=indicator.direction,
                unit=indicator.unit,
                value=float(raw_value) if _is_finite_number(raw_value) else None,
                passed=scored.passed,
                pontos=scored.pontos,
                pontos_possiveis=scored.pontos_possiveis,
                has_value=scored.has_value,
            )
        )

    total_pontos = sum(row.pontos for row in rows)
    total_peso = sum(indicator.peso for indicator in indicators)
    atendimento_mes = (total_pontos / SCORECARD_MONTHLY_POOL) * 100 if SCORECARD_MONTHLY_POOL else 0.0

    return ScorecardResult(
        rows=rows,
        total_pontos=total_pontos,
        total_peso=total_peso,
        pontos_possiveis_mes=SCORECARD_MONTHLY_POOL,
        atendimento_mes=atendimento_mes,
    )


# ---------------------------------------------------------------------------
# "ao vivo vence snapshot salvo" — porte de `effectiveByPeriod`
# (`ScorecardView.tsx`), que no TS só existe no frontend.
# ---------------------------------------------------------------------------


def read_snapshot_values(
    raw: Any, indicators: Sequence[ScorecardIndicator] = SC_INDICATORS
) -> dict[str, float | None]:
    """Extrai `{indicatorKey: value|None}` de `ScorecardSnapshot.raw`
    (`{"values": {...}}`), descartando qualquer chave fora de `SC_INDICATORS`
    e qualquer valor que não seja um número finito. Porte de
    `readSnapshotValues` (`src/app/api/scorecard/history/route.ts`)."""
    if not isinstance(raw, dict):
        return {}
    values = raw.get("values")
    if not isinstance(values, dict):
        return {}
    output: dict[str, float | None] = {}
    for indicator in indicators:
        value = values.get(indicator.key)
        output[indicator.key] = float(value) if _is_finite_number(value) else None
    return output


def merge_live_with_saved_fallback(
    live_values: Mapping[str, float | None],
    saved_values: Mapping[str, float | None] | None,
    indicators: Sequence[ScorecardIndicator] = SC_INDICATORS,
) -> dict[str, float | None]:
    """Mescla por indicador: o valor ao vivo sempre ganha de um snapshot
    salvo quando existir; o salvo só entra como respaldo quando o ao vivo
    não existe para aquele indicador/mês específico.

    Porte literal de `mergeWithSavedFallback` dentro de `effectiveByPeriod`
    (`src/features/scorecard/components/ScorecardView.tsx`, linhas ~321-334).
    "Salvar snapshot" não distingue um ajuste manual de um valor apenas
    puxado do módulo de origem — os dois são gravados como o mesmo número —
    então tratar o salvo como definitivo travaria o histórico na publicação
    que existia no momento do save, ignorando republicações mais recentes.
    """
    saved = saved_values or {}
    merged: dict[str, float | None] = {}
    for indicator in indicators:
        live_value = live_values.get(indicator.key)
        merged[indicator.key] = (
            float(live_value) if _is_finite_number(live_value) else saved.get(indicator.key)
        )
    return merged


# ---------------------------------------------------------------------------
# Camada 2 — Painel Geral consolidado (buildGeneralPanelData + applySpreadsheetScore)
# ---------------------------------------------------------------------------


@runtime_checkable
class PublishedByLike(Protocol):
    id: str
    name: str
    email: str


@runtime_checkable
class PublicationLike(Protocol):
    """Estrutura mínima exigida de uma `IndicatorPublication` (ORM ou DTO)."""

    id: str
    module: str
    indicator: str
    version: int
    active: bool
    payload: Any
    publishedAt: datetime
    publishedBy: PublishedByLike


def month_label_to_key(label: str) -> str | None:
    """Converte "Jan/2026" ou "Janeiro/2026" em "2026-01". Porte de
    `monthLabelToKey` (`src/features/scorecard/publications/index.ts`)."""
    text = str(label or "").strip()
    month_text, _, year_text = text.partition("/")
    normalized_month = month_text.strip().lower()
    month_index = -1
    for idx, name in enumerate(MONTH_NAMES):
        if name.lower() == normalized_month:
            month_index = idx
            break
    if month_index < 0:
        for idx, name in enumerate(MONTH_NAMES_FULL):
            if name.lower() == normalized_month:
                month_index = idx
                break
    try:
        year = int(year_text.strip())
    except (TypeError, ValueError):
        return None
    if month_index < 0 or year < 1900:
        return None
    return f"{year}-{month_index + 1:02d}"


def month_key_to_label(key: str) -> str:
    """"2026-06" -> "Jun/26" (ano com 2 dígitos, só para exibição)."""
    year_text, _, month_text = key.partition("-")
    try:
        month = int(month_text)
    except (TypeError, ValueError):
        month = 0
    name = MONTH_NAMES[month - 1] if 1 <= month <= 12 else "?"
    return f"{name}/{year_text[-2:]}"


@dataclass(slots=True)
class AdaptedPublication:
    current: float | None
    monthly: dict[str, float] = field(default_factory=dict)


def _payload_dict(payload: Any) -> dict[str, Any] | None:
    return payload if isinstance(payload, dict) else None


def _monthly_from_value_rows(rows: Any) -> dict[str, float]:
    monthly: dict[str, float] = {}
    if not isinstance(rows, list):
        return monthly
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = month_label_to_key(row.get("label", ""))
        value = row.get("v")
        if key and _is_finite_number(value):
            monthly[key] = float(value)
    return monthly


def _monthly_from_idp_rows(rows: Any) -> dict[str, float]:
    monthly: dict[str, float] = {}
    if not isinstance(rows, list):
        return monthly
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = month_label_to_key(row.get("label", ""))
        linha_base = row.get("linhaBase")
        has_valid_baseline = not isinstance(linha_base, int | float) or (
            not isinstance(linha_base, bool) and linha_base > 0
        )
        value = row.get("v")
        if key and has_valid_baseline and _is_finite_number(value):
            monthly[key] = float(value)
    return monthly


def _monthly_from_accident_rows(rows: Any) -> dict[str, float]:
    monthly: dict[str, float] = {}
    if not isinstance(rows, list):
        return monthly
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = month_label_to_key(row.get("label", ""))
        value = row.get("taxa")
        if key and _is_finite_number(value):
            monthly[key] = float(value)
    return monthly


def adapt_publication(key: str, publication: PublicationLike) -> AdaptedPublication:
    """Extrai `{current, monthly}` do payload de uma publicação, com o
    parser específico do indicador — porte de `adaptPublication`."""
    payload = _payload_dict(publication.payload)
    if payload is None:
        return AdaptedPublication(current=None)

    if key == "rdo":
        resultado, mensal = payload.get("resultado"), payload.get("mensal")
        if not _is_finite_number(resultado) or not isinstance(mensal, list):
            return AdaptedPublication(current=None)
        emitidos = payload.get("emitidos")
        current = float(resultado) if _is_finite_number(emitidos) and emitidos > 0 else None
        return AdaptedPublication(current=current, monthly=_monthly_from_value_rows(mensal))

    if key == "cronograma":
        resultado, mensal = payload.get("resultado"), payload.get("mensal")
        if not _is_finite_number(resultado) or not isinstance(mensal, list):
            return AdaptedPublication(current=None)
        total_linha_base = payload.get("totalLinhaBase")
        current = (
            float(resultado) if _is_finite_number(total_linha_base) and total_linha_base > 0 else None
        )
        return AdaptedPublication(current=current, monthly=_monthly_from_idp_rows(mensal))

    if key == "rnc":
        resultado, meta, mensal = payload.get("resultado"), payload.get("meta"), payload.get("mensal")
        if not _is_finite_number(resultado) or not _is_finite_number(meta) or not isinstance(mensal, list):
            return AdaptedPublication(current=None)
        return AdaptedPublication(current=float(resultado), monthly=_monthly_from_value_rows(mensal))

    if key == "5s":
        resultado, meta, mensal = payload.get("resultado"), payload.get("meta"), payload.get("mensal")
        if not _is_finite_number(resultado) or not _is_finite_number(meta) or not isinstance(mensal, list):
            return AdaptedPublication(current=None)
        return AdaptedPublication(current=float(resultado), monthly=_monthly_from_value_rows(mensal))

    if key == "taxa_acidentes":
        resultado, meta, mensal = payload.get("resultado"), payload.get("meta"), payload.get("mensal")
        if not _is_finite_number(resultado) or not _is_finite_number(meta) or not isinstance(mensal, list):
            return AdaptedPublication(current=None)
        return AdaptedPublication(current=float(resultado), monthly=_monthly_from_accident_rows(mensal))

    return AdaptedPublication(current=None)


def published_value_for_period(
    key: str, publication: PublicationLike, year: int, month: int
) -> float | None:
    """Valor mensal publicado de um indicador para o período solicitado."""
    adapted = adapt_publication(key, publication)
    return adapted.monthly.get(f"{year}-{month:02d}")


def latest_published_value_for_period(
    key: str, publications: Sequence[PublicationLike], year: int, month: int
) -> float | None:
    """Percorre o histórico de publicações (mais nova -> mais antiga) até
    achar um valor válido para o mês pedido. Só entra em ação se existir ao
    menos uma publicação ATIVA — sem essa guarda, um indicador totalmente
    retratado (fonte apagada, nada republicado) reviveria valores de
    publicações antigas/desativadas para sempre.

    Porte literal de `latestPublishedValueForPeriod`
    (`src/features/scorecard/publications/index.ts`, linhas 286-307).
    """
    if not any(publication.active is True for publication in publications):
        return None

    ordered = sorted(
        publications,
        key=lambda publication: (publication.active is True, publication.publishedAt, publication.version),
        reverse=True,
    )
    for publication in ordered:
        value = published_value_for_period(key, publication, year, month)
        if value is not None:
            return value
    return None


def _publications_for_indicator(
    indicator: ScorecardIndicator, publications: Sequence[PublicationLike]
) -> list[PublicationLike]:
    if indicator.source is None:
        return []
    matching = [
        publication
        for publication in publications
        if publication.module == indicator.source.module
        and publication.indicator == indicator.source.indicator
    ]
    matching.sort(
        key=lambda publication: (publication.active is True, publication.publishedAt, publication.version),
        reverse=True,
    )
    return matching


def passes_panel_target(indicator: ScorecardIndicator, value: float | None) -> bool | None:
    if not _is_finite_number(value):
        return None
    assert value is not None
    return value <= indicator.meta if indicator.direction == "lower" else value >= indicator.meta


def percent_of_target(indicator: ScorecardIndicator, value: float | None) -> float | None:
    if not _is_finite_number(value):
        return None
    assert value is not None
    if indicator.direction == "lower":
        return (indicator.meta / value) * 100 if value > 0 else 100.0
    return (value / indicator.meta) * 100 if indicator.meta else None


@dataclass(slots=True)
class GeneralPanelMonthCell:
    key: str
    label: str
    value: float | None
    passed: bool | None
    pct_of_meta: float | None


@dataclass(slots=True)
class PublicationRef:
    id: str
    version: int
    published_at: datetime
    published_by_id: str
    published_by_name: str
    published_by_email: str


@dataclass(slots=True)
class GeneralPanelIndicator:
    key: str
    label: str
    short_label: str
    peso: float
    meta: float
    direction: str
    unit: str
    result: float | None
    has_data: bool
    passed: bool | None
    partial: float | None
    partial_pass: bool | None
    months: list[GeneralPanelMonthCell]
    publication: PublicationRef | None


@dataclass(slots=True)
class GeneralPanelData:
    has_data: bool
    month_keys: list[str]
    month_labels: list[str]
    pontuacao_prevista: float
    pontuacao_prevista_semestre: float
    pontos_realizados: float
    atendimento_geral: float
    percentual_semestre_completo: float
    """Extensão explícita deste projeto (não existe no código TS original):
    `pontosRealizados / SCORECARD_MAX_POINTS (11.582) * 100` — percentual
    contra o semestre COMPLETO, sempre, independentemente de quantos meses
    têm dado disponível."""
    percentual_dados_disponiveis: float
    """Extensão explícita deste projeto: mesmo valor de `atendimento_geral`
    (percentual contra o denominador proporcional aos meses com dado),
    exposto sob o nome pedido pela especificação desta migração, ao lado de
    `atendimento_geral` (preservado por compatibilidade de nome com o TS)."""
    reference_date: datetime | None
    indicators: list[GeneralPanelIndicator]


def compute_general_panel(
    publications: Sequence[PublicationLike],
    period: PeriodRange | None,
    indicators: Sequence[ScorecardIndicator] = SC_INDICATORS,
    snapshot_values: Mapping[str, Mapping[str, float | None]] | None = None,
) -> GeneralPanelData:
    """Consolida o Painel Geral para o `period` pedido.

    Unifica em uma única função as duas camadas do TS
    (`buildGeneralPanelData` + `applySpreadsheetScore`, ver
    `src/app/api/dashboard/route.ts`): a seleção da publicação vencedora por
    indicador prioriza uma versão que tenha ao menos um mês dentro de
    `period` (senão cai na mais recente de qualquer período); os meses
    exibidos são sempre filtrados para dentro de `period`; nenhum valor é
    arredondado (arredondamento é só de apresentação) — replicando o
    comportamento observável da rota HTTP real (que sempre aplica
    `applySpreadsheetScore` por cima de `buildGeneralPanelData`, descartando
    o `Math.round` intermediário da camada base).

    `period=None` reproduz o comportamento de `buildGeneralPanelData`
    chamada isoladamente sem período (como fazem alguns testes unitários):
    nenhuma preferência de seleção por período e nenhum filtro de meses. A
    rota HTTP real (`GET /dashboard`) sempre resolve um período concreto
    (query > `AppSetting` salvo > ciclo vigente) antes de chamar esta
    função — `period=None` nunca ocorre no caminho HTTP real.

    `snapshot_values` (opcional): mapa `{"YYYY-MM": {indicatorKey: valor}}`
    de `ScorecardSnapshot` já lidos do banco. Extensão mandatada por esta
    migração (não existe no TS original, onde o Painel Geral nunca lê
    `ScorecardSnapshot`): quando a publicação vencedora de um indicador não
    tem valor para um mês que já está sendo exibido (porque outro indicador
    tem publicação para aquele mês), o snapshot salvo entra como respaldo —
    mesma regra de precedência de `merge_live_with_saved_fallback`, aplicada
    célula a célula. Deliberadamente NÃO expande o conjunto de meses
    exibidos além do que as publicações reais já estabeleceram, para não
    reviver o bug real que motivou "só a publicação mais recente conta,
    sem herdar meses de versões antigas" (ver comentário em
    `_publications_for_indicator`/teste correspondente).
    """
    snapshot_values = snapshot_values or {}
    allowed_month_keys: set[str] | None = (
        {f"{item.year}-{item.month:02d}" for item in enumerate_period_months(period)}
        if period is not None
        else None
    )

    adapted_by_key: dict[str, tuple[PublicationLike, AdaptedPublication]] = {}
    raw_month_key_set: set[str] = set()

    for indicator in indicators:
        candidates = _publications_for_indicator(indicator, publications)
        if not candidates:
            continue

        if allowed_month_keys is not None:
            latest = next(
                (
                    candidate
                    for candidate in candidates
                    if any(
                        key in allowed_month_keys
                        for key in adapt_publication(indicator.key, candidate).monthly
                    )
                ),
                candidates[0],
            )
        else:
            latest = candidates[0]

        adapted = adapt_publication(indicator.key, latest)
        adapted_by_key[indicator.key] = (latest, adapted)
        raw_month_key_set.update(adapted.monthly.keys())

    month_keys = sorted(
        raw_month_key_set
        if allowed_month_keys is None
        else (key for key in raw_month_key_set if key in allowed_month_keys)
    )
    month_labels = [month_key_to_label(key) for key in month_keys]

    pontos_realizados = 0.0
    result_indicators: list[GeneralPanelIndicator] = []

    for indicator in indicators:
        entry = adapted_by_key.get(indicator.key)
        publication: PublicationLike | None = entry[0] if entry else None
        adapted_entry: AdaptedPublication | None = entry[1] if entry else None
        current = adapted_entry.current if adapted_entry else None

        months: list[GeneralPanelMonthCell] = []
        month_values: list[float] = []
        for key in month_keys:
            raw_value = adapted_entry.monthly.get(key) if adapted_entry else None
            if raw_value is None:
                fallback = snapshot_values.get(key, {}).get(indicator.key)
                if _is_finite_number(fallback):
                    raw_value = float(fallback)
            passed = passes_panel_target(indicator, raw_value)
            months.append(
                GeneralPanelMonthCell(
                    key=key,
                    label=month_key_to_label(key),
                    value=raw_value,
                    passed=passed,
                    pct_of_meta=percent_of_target(indicator, raw_value),
                )
            )
            if raw_value is not None:
                month_values.append(raw_value)
                if passed:
                    pontos_realizados += (indicator.peso / 100) * SCORECARD_MONTHLY_POOL

        partial = (sum(month_values) / len(month_values)) if month_values else None

        result_indicators.append(
            GeneralPanelIndicator(
                key=indicator.key,
                label=indicator.label,
                short_label=SHORT_LABELS.get(indicator.key, indicator.label),
                peso=indicator.peso,
                meta=indicator.meta,
                direction=indicator.direction,
                unit=indicator.unit,
                result=current,
                has_data=len(month_values) > 0,
                passed=passes_panel_target(indicator, current),
                partial=partial,
                partial_pass=passes_panel_target(indicator, partial),
                months=months,
                publication=(
                    PublicationRef(
                        id=publication.id,
                        version=publication.version,
                        published_at=publication.publishedAt,
                        published_by_id=publication.publishedBy.id,
                        published_by_name=publication.publishedBy.name,
                        published_by_email=publication.publishedBy.email,
                    )
                    if publication
                    else None
                ),
            )
        )

    pontuacao_prevista = len(month_keys) * SCORECARD_MONTHLY_POOL
    atendimento_geral = (pontos_realizados / pontuacao_prevista) * 100 if pontuacao_prevista > 0 else 0.0
    percentual_semestre_completo = (pontos_realizados / SCORECARD_MAX_POINTS) * 100

    reference_date = max((p.publishedAt for p in publications), default=None)

    return GeneralPanelData(
        has_data=any(indicator.has_data for indicator in result_indicators),
        month_keys=month_keys,
        month_labels=month_labels,
        pontuacao_prevista=pontuacao_prevista,
        pontuacao_prevista_semestre=float(SCORECARD_MAX_POINTS),
        pontos_realizados=pontos_realizados,
        atendimento_geral=atendimento_geral,
        percentual_semestre_completo=percentual_semestre_completo,
        percentual_dados_disponiveis=atendimento_geral,
        reference_date=reference_date,
        indicators=result_indicators,
    )
