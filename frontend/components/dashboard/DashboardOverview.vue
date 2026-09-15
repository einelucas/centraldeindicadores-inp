<script setup lang="ts">
import { Medal, Percent, RefreshCw, Trophy } from "lucide-vue-next";
import type { DashboardResponse, PeriodRange } from "~/types/api";
import { currentOperationalPeriod, periodToQuery } from "~/utils/period";
import { formatDate, formatNumber } from "~/utils/format";
import { generalIndicatorColor } from "~/utils/scorecard-color";
import { SCORECARD_INDICATOR_ROUTES } from "~/utils/scorecard-routes";

const indicatorRoutes = SCORECARD_INDICATOR_ROUTES;

const api = useApi();
const period = ref<PeriodRange>(currentOperationalPeriod());
const data = ref<DashboardResponse | null>(null);
const loading = ref(true);
const error = ref("");

async function load() {
  loading.value = true;
  error.value = "";
  try {
    data.value = await api.get<DashboardResponse>(
      "/dashboard",
      periodToQuery(period.value),
    );
  } catch (cause) {
    error.value =
      cause instanceof Error
        ? cause.message
        : "Erro ao carregar o Painel Geral.";
  } finally {
    loading.value = false;
  }
}

watch(period, load, { deep: true });
onMounted(load);

const atendimentoColor = computed(() =>
  generalIndicatorColor(data.value?.atendimentoGeral ?? 0),
);

const atendimentoDisplay = computed(
  () => `${formatNumber(data.value?.atendimentoGeral ?? 0, 2)}%`,
);

const atendimentoAtivosDisplay = computed(
  () => `${formatNumber(data.value?.atendimentoAtivosGeral ?? 0, 2)}%`,
);

const semestreContabilizavel = computed(() => {
  if (!data.value) return 0;
  return (
    (data.value.pontuacaoPrevistaSemestre * data.value.coberturaAtivaPct) / 100
  );
});

const semestreReservado = computed(() => {
  if (!data.value) return 0;
  return data.value.pontuacaoPrevistaSemestre - semestreContabilizavel.value;
});

function formatPoints(value: number, decimals = 2) {
  return value.toLocaleString("pt-BR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

const executiveDescription = computed(() => {
  if (!data.value) return "";
  let text = `Referência: ${formatDate(data.value.referenceDate, true)}`;
  if (data.value.monthLabels.length) {
    text += ` · Período: ${data.value.monthLabels[0]}`;
    if (data.value.monthLabels.length > 1)
      text += ` – ${data.value.monthLabels.at(-1)}`;
  }
  return text;
});
</script>

<template>
  <section class="surface scorecard-dashboard">
    <header class="surface-header">
      <div>
        <h2>Painel Geral</h2>
        <p>Indicadores consolidados a partir das publicações ativas.</p>
      </div>
      <div class="toolbar scorecard-period-toolbar">
        <PeriodSelector v-model="period" />
        <button
          class="btn btn-icon"
          type="button"
          :disabled="loading"
          aria-label="Atualizar Painel Geral"
          @click="load"
        >
          <RefreshCw :size="16" />
        </button>
      </div>
    </header>

    <div v-if="loading && !data" class="loading-state">
      <div class="spinner" />
    </div>
    <div v-else-if="error" class="error-state">
      <div>
        <h3>Não foi possível carregar o Painel Geral</h3>
        <p>{{ error }}</p>
      </div>
    </div>
    <div v-else-if="!data?.hasData" class="empty-state">
      <div>
        <h3>Nenhum indicador publicado neste período</h3>
        <p>As publicações dos módulos aparecerão aqui após serem concluídas.</p>
      </div>
    </div>

    <div v-else-if="data" class="surface-body scorecard-dashboard-body">
      <div class="scorecard-summary-grid">
        <article class="scorecard-summary-card">
          <div class="scorecard-summary-head">
            <span class="scorecard-summary-label"
              >Pontuação oficial — semestre</span
            >
            <span class="scorecard-summary-icon" aria-hidden="true"
              ><Trophy
            /></span>
          </div>
          <strong class="scorecard-summary-value">{{
            formatPoints(data.pontuacaoPrevistaSemestre)
          }}</strong>
          <span class="scorecard-summary-detail">
            {{ formatPoints(semestreContabilizavel) }} contabilizáveis ({{
              formatNumber(data.coberturaAtivaPct, 0)
            }}%) · {{ formatPoints(semestreReservado) }} reservados (Horas
            Extras)
          </span>
        </article>

        <article class="scorecard-summary-card">
          <div class="scorecard-summary-head">
            <span class="scorecard-summary-label"
              >Pontuação prevista — período</span
            >
            <span class="scorecard-summary-icon" aria-hidden="true"
              ><Trophy
            /></span>
          </div>
          <strong class="scorecard-summary-value">{{
            formatPoints(data.pontuacaoPrevista)
          }}</strong>
          <span class="scorecard-summary-detail"
            >Meta dos {{ data.monthKeys.length }} mês(es) com dados</span
          >
        </article>

        <article
          class="scorecard-summary-card is-highlighted"
          style="--scorecard-accent: #eaa239"
        >
          <div class="scorecard-summary-head">
            <span class="scorecard-summary-label">Pontos realizados</span>
            <span class="scorecard-summary-icon" aria-hidden="true"
              ><Medal
            /></span>
          </div>
          <strong class="scorecard-summary-value">{{
            data.pontosRealizados.toLocaleString("pt-BR")
          }}</strong>
          <span class="scorecard-summary-detail"
            >Acumulado no período com dados</span
          >
        </article>

        <article
          class="scorecard-summary-card is-highlighted"
          :style="{ '--scorecard-accent': atendimentoColor }"
        >
          <div class="scorecard-summary-head">
            <span class="scorecard-summary-label">Atendimento geral</span>
            <span class="scorecard-summary-icon" aria-hidden="true"
              ><Percent
            /></span>
          </div>
          <strong class="scorecard-summary-value">{{
            atendimentoDisplay
          }}</strong>
          <span class="scorecard-summary-detail">
            Realizado ÷ previsto oficial · {{ atendimentoAtivosDisplay }} entre
            os indicadores ativos
          </span>
        </article>
      </div>

      <section
        class="scorecard-executive-card"
        aria-labelledby="scorecard-executive-title"
      >
        <ScorecardExecutivePanel
          :data="data"
          variant="published"
          :description="executiveDescription"
          :indicator-routes="indicatorRoutes"
        />

        <div class="scorecard-legend-grid">
          <section class="scorecard-subcard">
            <h4 class="scorecard-section-title">
              Legenda · Indicadores gerais
            </h4>
            <p class="scorecard-section-description">
              Faixas de leitura do atendimento consolidado.
            </p>
            <div class="scorecard-legend-row">
              <span class="scorecard-legend-dot is-green" />
              <div><strong>≥ 95%</strong><span>Valor atendido</span></div>
            </div>
            <div class="scorecard-legend-row">
              <span class="scorecard-legend-dot is-amber" />
              <div><strong>70% a 94,99%</strong><span>Atenção</span></div>
            </div>
            <div class="scorecard-legend-row">
              <span class="scorecard-legend-dot is-red" />
              <div><strong>&lt; 70%</strong><span>Fora da meta</span></div>
            </div>
          </section>

          <section class="scorecard-subcard">
            <h4 class="scorecard-section-title">
              Legenda · Indicadores setoriais
            </h4>
            <p class="scorecard-section-description">
              Faixas de leitura para os indicadores setoriais (por unidade).
            </p>
            <div class="scorecard-legend-row">
              <span class="scorecard-legend-dot is-green" />
              <div><strong>≥ 95%</strong><span>Valor atendido</span></div>
            </div>
            <div class="scorecard-legend-row">
              <span class="scorecard-legend-dot is-teal" />
              <div><strong>90% a 94,99%</strong><span>90%</span></div>
            </div>
            <div class="scorecard-legend-row">
              <span class="scorecard-legend-dot is-blue" />
              <div><strong>80% a 89,99%</strong><span>80%</span></div>
            </div>
            <div class="scorecard-legend-row">
              <span class="scorecard-legend-dot is-amber" />
              <div><strong>70% a 79,99%</strong><span>70%</span></div>
            </div>
            <div class="scorecard-legend-row">
              <span class="scorecard-legend-dot is-red" />
              <div><strong>&lt; 70%</strong><span>Sem setorial</span></div>
            </div>
          </section>
        </div>
      </section>
    </div>
  </section>
</template>
