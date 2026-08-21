<script setup lang="ts">
import { Download, FileSpreadsheet, RefreshCw } from "lucide-vue-next";
import type { PeriodRange, PublicationEnvelope } from "~/types/api";
import { currentOperationalPeriod, periodToQuery } from "~/utils/period";
import { formatDate, formatNumber, formatPercent } from "~/utils/format";

const props = defineProps<{ module: "rdo" | "idp" | "rnc" | "cinco-s" | "taxa-acidentes"; title: string }>();
const api = useApi();
const exporter = useExport();
const period = ref<PeriodRange>(currentOperationalPeriod());
const publication = ref<PublicationEnvelope["publication"]>(null);
const loading = ref(true);
const error = ref("");

const payload = computed<Record<string, unknown>>(() => publication.value?.payload ?? {});
const target = computed(() => Number(payload.value.meta ?? publication.value?.target ?? 0));
const monthly = computed(() => {
  const rows = Array.isArray(payload.value.mensal) ? payload.value.mensal as Array<Record<string, unknown>> : [];
  return rows.map(row => ({ label: String(row.label ?? ""), value: typeof row.v === "number" ? row.v : typeof row.taxa === "number" ? row.taxa : null }));
});
const units = computed(() => {
  const rows = Array.isArray(payload.value.unidades) ? payload.value.unidades as Array<Record<string, unknown>> : [];
  if (props.module !== "taxa-acidentes") return rows.slice(0, 14).map(row => ({ label: String(row.n ?? ""), value: typeof row.v === "number" ? row.v : null }));
  const totals = new Map<string, number>();
  for (const row of rows) totals.set(String(row.unidade ?? ""), (totals.get(String(row.unidade ?? "")) ?? 0) + Number(row.caf ?? 0) + Number(row.saf ?? 0));
  return [...totals].map(([label, value]) => ({ label, value })).sort((a,b) => b.value-a.value).slice(0,14);
});

const metrics = computed<Array<[string, string]>>(() => {
  const p = payload.value;
  if (props.module === "rdo") return [
    ["Aprovação", formatPercent(p.resultado)], ["Meta", formatPercent(p.meta)],
    ["Aprovados", formatNumber(p.aprovados)], ["Emitidos", formatNumber(p.emitidos)],
  ];
  if (props.module === "idp") return [
    ["Aderência", formatPercent(p.resultado)], ["Meta", formatPercent(p.meta)],
    ["Linha de base", formatNumber(p.totalLinhaBase)], ["Execução real", formatNumber(p.totalReal)],
  ];
  if (props.module === "rnc") return [
    ["Prazo médio", `${formatNumber(p.resultado, 1)} dias`], ["Meta", `${formatNumber(p.meta, 1)} dias`],
    ["Resolvidas", formatNumber(p.semestreResolvidas)], ["Total", formatNumber(p.semestreTotal)],
  ];
  if (props.module === "cinco-s") return [
    ["Aderência geral", formatPercent(p.resultado)], ["Meta", formatPercent(p.meta)],
    ["Unidades", formatNumber((p.unidades as unknown[])?.length ?? 0)], ["Meses", formatNumber((p.mensal as unknown[])?.length ?? 0)],
  ];
  return [
    ["Taxa consolidada", formatNumber(p.resultado, 2)], ["Meta", formatNumber(p.meta, 2)],
    ["Acidentes CAF", formatNumber(p.acidentesCaf)], ["Acidentes SAF", formatNumber(p.acidentesSaf)],
  ];
});

async function load() {
  loading.value = true; error.value = "";
  try {
    const response = await api.get<PublicationEnvelope>(`/publicacoes/${props.module}`, periodToQuery(period.value));
    publication.value = response.publication;
  } catch (cause) { error.value = cause instanceof Error ? cause.message : "Erro ao carregar painel."; }
  finally { loading.value = false; }
}

function exportRows() {
  return monthly.value.map(item => ({ período: item.label, resultado: item.value, meta: target.value }));
}

watch(period, load, { deep: true });
onMounted(load);
</script>

<template>
  <div class="stack">
    <div class="surface">
      <div class="surface-header">
        <div><h2>{{ title }}</h2><p v-if="publication">Publicação v{{ publication.version }} · {{ formatDate(publication.publishedAt, true) }}</p></div>
        <div class="toolbar">
          <PeriodSelector v-model="period" />
          <button class="btn btn-icon" title="Atualizar" :disabled="loading" @click="load"><RefreshCw :size="16" /></button>
          <button class="btn btn-icon" title="Excel" :disabled="!publication" @click="exporter.excel(`${module}-painel`, exportRows())"><FileSpreadsheet :size="16" /></button>
          <button class="btn btn-icon" title="PDF" :disabled="!publication" @click="exporter.pdf(`${module}-painel`, title, exportRows())"><Download :size="16" /></button>
        </div>
      </div>
      <div v-if="loading && !publication" class="loading-state"><div class="spinner" /></div>
      <div v-else-if="error" class="error-state"><div><h3>Não foi possível carregar o painel</h3><p>{{ error }}</p><button class="btn mt-3" @click="load">Tentar novamente</button></div></div>
      <div v-else-if="!publication" class="empty-state"><div><h3>Nenhuma publicação para este período</h3><p>Selecione outro semestre ou publique os dados na área de Administração.</p></div></div>
      <div v-else class="surface-body stack">
        <div class="metric-grid">
          <MetricCard v-for="metric in metrics" :key="metric[0]" :label="metric[0]" :value="metric[1]" />
        </div>
        <div class="chart-grid">
          <section class="surface chart-card"><h3>Evolução mensal</h3><p>Resultado publicado ao longo do período.</p><LineChart :points="monthly" :target="target" :suffix="module === 'taxa-acidentes' || module === 'rnc' ? '' : '%'" /></section>
          <section class="surface chart-card"><h3>{{ module === 'taxa-acidentes' ? 'Acidentes por unidade' : 'Resultado por unidade' }}</h3><p>Comparativo das unidades incluídas na publicação.</p><BarChart :points="units" :target="module === 'taxa-acidentes' ? null : target" :suffix="module === 'taxa-acidentes' ? '' : '%'" /></section>
        </div>
        <div class="table-wrap">
          <table class="data-table"><thead><tr><th>Período</th><th class="numeric">Resultado</th><th class="numeric">Meta</th><th>Status</th></tr></thead>
            <tbody><tr v-for="item in monthly" :key="item.label"><td>{{ item.label }}</td><td class="numeric">{{ formatNumber(item.value, 2) }}</td><td class="numeric">{{ formatNumber(target, 2) }}</td><td><span class="badge" :class="item.value !== null && (module === 'rnc' || module === 'taxa-acidentes' ? item.value <= target : item.value >= target) ? 'good' : 'bad'">{{ item.value !== null && (module === 'rnc' || module === 'taxa-acidentes' ? item.value <= target : item.value >= target) ? 'Meta atingida' : 'Abaixo da meta' }}</span></td></tr></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
