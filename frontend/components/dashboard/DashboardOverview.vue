<script setup lang="ts">
import { RefreshCw } from "lucide-vue-next";
import type { DashboardResponse, PeriodRange } from "~/types/api";
import { currentOperationalPeriod, periodToQuery } from "~/utils/period";
import { formatDate, formatNumber, formatPercent } from "~/utils/format";

const api = useApi();
const period = ref<PeriodRange>(currentOperationalPeriod());
const data = ref<DashboardResponse | null>(null);
const loading = ref(true);
const error = ref("");

async function load() {
  loading.value = true; error.value = "";
  try { data.value = await api.get<DashboardResponse>("/dashboard", periodToQuery(period.value)); }
  catch (cause) { error.value = cause instanceof Error ? cause.message : "Erro ao carregar o Painel Geral."; }
  finally { loading.value = false; }
}
watch(period, load, { deep: true });
onMounted(load);
</script>

<template>
  <section class="surface">
    <header class="surface-header">
      <div><h2>Painel Geral</h2><p>Indicadores consolidados a partir das publicações ativas.</p></div>
      <div class="toolbar"><PeriodSelector v-model="period" /><button class="btn btn-icon" :disabled="loading" @click="load"><RefreshCw :size="16" /></button></div>
    </header>
    <div v-if="loading && !data" class="loading-state"><div class="spinner" /></div>
    <div v-else-if="error" class="error-state"><div><h3>Não foi possível carregar o Painel Geral</h3><p>{{ error }}</p></div></div>
    <div v-else-if="!data?.hasData" class="empty-state"><div><h3>Nenhum indicador publicado neste período</h3><p>As publicações dos módulos aparecerão aqui após serem concluídas.</p></div></div>
    <div v-else-if="data" class="surface-body stack">
      <div class="metric-grid">
        <MetricCard label="Pontos realizados" :value="formatNumber(data.pontosRealizados, 1)" :detail="`de ${formatNumber(data.pontuacaoPrevistaSemestre, 1)} no semestre`" />
        <MetricCard label="Atendimento geral" :value="formatPercent(data.atendimentoGeral)" />
        <MetricCard label="Dados disponíveis" :value="formatPercent(data.percentualDadosDisponiveis)" />
        <MetricCard label="Semestre completo" :value="formatPercent(data.percentualSemestreCompleto)" :detail="data.referenceDate ? `Referência: ${formatDate(data.referenceDate)}` : ''" />
      </div>
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Indicador</th><th class="numeric">Peso</th><th class="numeric">Meta</th><th v-for="label in data.monthLabels" :key="label" class="numeric">{{ label }}</th><th class="numeric">Resultado</th><th class="numeric">Pontos</th></tr></thead>
          <tbody><tr v-for="indicator in data.indicators" :key="indicator.key"><td><strong>{{ indicator.label }}</strong></td><td class="numeric">{{ formatPercent(indicator.peso) }}</td><td class="numeric">{{ formatNumber(indicator.meta, 2) }}{{ indicator.unit }}</td><td v-for="month in indicator.months" :key="month.key" class="numeric"><span class="badge" :class="month.passed === true ? 'good' : month.passed === false ? 'bad' : ''">{{ month.value === null ? '—' : `${formatNumber(month.value, 2)}${indicator.unit}` }}</span></td><td class="numeric"><strong>{{ indicator.result === null ? '—' : `${formatNumber(indicator.result, 2)}${indicator.unit}` }}</strong></td><td class="numeric">{{ formatNumber(indicator.partial, 1) }}</td></tr></tbody>
        </table>
      </div>
    </div>
  </section>
</template>
