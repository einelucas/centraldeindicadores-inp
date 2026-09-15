<script setup lang="ts">
import {
  SCORECARD_MAX_POINTS,
  SCORECARD_MONTHLY_POOL,
} from "~/logic/features/scorecard/types";
import type { DashboardIndicator, DashboardResponse } from "~/types/api";
import { formatNumber } from "~/utils/format";

const props = withDefaults(
  defineProps<{
    data: DashboardResponse;
    /** `published` mantém a densidade compacta atual do Painel Geral;
     * `admin` usa linhas, células mensais, badges e rodapé mais altos,
     * nas proporções do admin do Scorecard no Next legado. */
    variant?: "published" | "admin";
    title?: string;
    description?: string;
    /** Rota Nuxt do módulo de origem, por chave de indicador. Uma célula só
     * vira link quando a chave tem rota própria e funcional aqui. */
    indicatorRoutes?: Record<string, string>;
  }>(),
  {
    variant: "published",
    title: "Resumo Executivo",
    description: "",
    indicatorRoutes: () => ({}),
  },
);

function formatPoints(value: number, decimals = 2) {
  return value.toLocaleString("pt-BR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function formatValue(indicator: DashboardIndicator, value: number | null) {
  if (value === null || !Number.isFinite(value)) return "—";
  if (indicator.unit === "dias") return `${Math.round(value)}`;
  if (indicator.unit === "%") return `${value.toFixed(1)}%`;
  return value.toFixed(1);
}

function formatMeta(indicator: DashboardIndicator) {
  if (!indicator.scoringEnabled) {
    if (indicator.key === "horas_extras" && indicator.meta !== null)
      return `≤${formatNumber(indicator.meta, 0)}%`;
    return indicator.meta !== null ? formatNumber(indicator.meta, 0) : "—";
  }
  const operator = indicator.direction === "lower" ? "≤" : "≥";
  const suffix = indicator.unit === "dias" ? " dias" : indicator.unit;
  return `${operator}${formatNumber(indicator.meta ?? 0, 2)}${suffix}`;
}

function indicatorPoints(indicator: DashboardIndicator) {
  return indicator.months.reduce(
    (total, month) =>
      total +
      (month.passed ? (indicator.peso / 100) * SCORECARD_MONTHLY_POOL : 0),
    0,
  );
}

function indicatorMaxPoints(indicator: DashboardIndicator) {
  return (indicator.peso / 100) * SCORECARD_MAX_POINTS;
}

const monthlyPointTotals = computed(() =>
  props.data.monthKeys.map((key) =>
    props.data.indicators.reduce((total, indicator) => {
      const month = indicator.months.find((item) => item.key === key);
      return (
        total +
        (month?.passed ? (indicator.peso / 100) * SCORECARD_MONTHLY_POOL : 0)
      );
    }, 0),
  ),
);

const atendimentoDisplay = computed(
  () => `${formatNumber(props.data.atendimentoGeral, 2)}%`,
);
</script>

<template>
  <header class="scorecard-executive-header">
    <h3 id="scorecard-executive-title">{{ title }}</h3>
    <span v-if="description">{{ description }}</span>
  </header>

  <div class="scorecard-subcard scorecard-results-card">
    <h4 class="scorecard-section-title">Resultado geral do PPR Obras</h4>
    <p class="scorecard-section-description">
      Leitura consolidada dos indicadores e pesos mensais. Dados administrativos
      não publicados não entram neste quadro.
    </p>

    <div class="scorecard-table-wrap">
      <table
        class="scorecard-table"
        :class="{ 'is-admin': variant === 'admin' }"
      >
        <colgroup>
          <col class="scorecard-col-indicator" />
          <col class="scorecard-col-weight" />
          <col class="scorecard-col-target" />
          <col
            v-for="label in data.monthLabels"
            :key="label"
            class="scorecard-col-month"
          />
          <col class="scorecard-col-average" />
          <col class="scorecard-col-points" />
          <col class="scorecard-col-status" />
        </colgroup>
        <thead>
          <tr>
            <th>Indicador</th>
            <th class="numeric">Peso</th>
            <th class="numeric">Meta</th>
            <th
              v-for="label in data.monthLabels"
              :key="label"
              class="text-center"
            >
              {{ label }}
            </th>
            <th class="numeric">Média</th>
            <th class="numeric">Pontos</th>
            <th class="text-center">Situação</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="indicator in data.indicators" :key="indicator.key">
            <td class="scorecard-indicator-name">{{ indicator.label }}</td>
            <td class="numeric scorecard-brand-emphasis">
              {{ formatPoints(indicator.peso) }}%
            </td>
            <td class="numeric scorecard-table-emphasis">
              {{ formatMeta(indicator) }}
            </td>
            <td
              v-for="month in indicator.months"
              :key="month.key"
              class="scorecard-month-cell"
            >
              <NuxtLink
                v-if="indicatorRoutes[indicator.key]"
                :to="indicatorRoutes[indicator.key]"
                class="scorecard-month-value"
                :class="
                  month.value === null
                    ? 'is-empty'
                    : month.passed
                      ? 'is-good'
                      : 'is-bad'
                "
                :title="`${indicator.label} — ${month.label}: ver detalhes`"
                >{{ formatValue(indicator, month.value) }}</NuxtLink
              >
              <span
                v-else
                class="scorecard-month-value"
                :class="
                  month.value === null
                    ? 'is-empty'
                    : month.passed
                      ? 'is-good'
                      : 'is-bad'
                "
                >{{ formatValue(indicator, month.value) }}</span
              >
            </td>
            <td class="numeric scorecard-table-emphasis">
              {{ formatValue(indicator, indicator.partial) }}
            </td>
            <td class="numeric">
              <strong class="scorecard-points">{{
                formatPoints(indicatorPoints(indicator))
              }}</strong>
              <span class="scorecard-points-maximum"
                >de {{ formatPoints(indicatorMaxPoints(indicator)) }}</span
              >
            </td>
            <td class="text-center">
              <span
                v-if="!indicator.scoringEnabled"
                class="scorecard-status is-dev"
                >Em desenvolvimento</span
              >
              <span
                v-else-if="indicator.partialPass === null"
                class="scorecard-no-data"
                >Sem dados</span
              >
              <span
                v-else
                class="scorecard-status"
                :class="indicator.partialPass ? 'is-good' : 'is-bad'"
              >
                {{ indicator.partialPass ? "Dentro da meta" : "Fora da meta" }}
              </span>
            </td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td colspan="3">Pontuação mensal</td>
            <td
              v-for="(key, index) in data.monthKeys"
              :key="key"
              class="text-center"
            >
              {{ formatPoints(monthlyPointTotals[index] ?? 0) }}
            </td>
            <td class="numeric">—</td>
            <td class="numeric scorecard-total-points">
              {{ data.pontosRealizados.toLocaleString("pt-BR") }}
            </td>
            <td class="text-center">{{ atendimentoDisplay }}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  </div>
</template>
