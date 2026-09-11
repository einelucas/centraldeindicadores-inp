<script setup lang="ts">
import { RotateCw, Save, Trash2 } from "lucide-vue-next";
import { joinWithAnd, nextWorkingPeriod } from "~/composables/usePublicationPeriodOptions";
import { SCORECARD_INDICATOR_ROUTES } from "~/utils/scorecard-routes";
import { SCORECARD_MAX_POINTS, SCORECARD_MONTHLY_POOL } from "~/logic/features/scorecard/types";
import type { DashboardResponse, PeriodRange, ScorecardComputation } from "~/types/api";
import { cycleFromYearSemester, MONTHS, periodToQuery, yearSemesterFromCycle, type Semester } from "~/utils/period";
import { INDICATOR_DATA_CHANGED_EVENT } from "~/utils/browser-events";

defineProps<{ canClear: boolean }>();

const api = useApi();
const { year, semester, cycle: period, setPeriod } = useReadingContextCycle();
const { availablePeriods, periodOptions, loadAvailablePeriods } =
  usePublicationPeriodOptions("scorecard", year, semester);

const rows = ref<ScorecardComputation[]>([]);
const loading = ref(true);
const busy = ref(false);
const message = ref("");
const tone = ref<"success" | "error">("success");
const initialized = ref(false);
const lastSyncedAt = ref<Date | null>(null);

const dashboardData = ref<DashboardResponse | null>(null);
const dashboardLoading = ref(true);
const dashboardError = ref("");
let refreshTimer: ReturnType<typeof setInterval> | null = null;

function competencies(range: PeriodRange) {
  const result: Array<{ year: number; month: number }> = [];
  let currentYear = range.startYear;
  let currentMonth = range.startMonth;
  while (currentYear < range.endYear || (currentYear === range.endYear && currentMonth <= range.endMonth)) {
    result.push({ year: currentYear, month: currentMonth });
    currentMonth++;
    if (currentMonth === 13) {
      currentMonth = 1;
      currentYear++;
    }
  }
  return result;
}

function notify(text: string, kind: "success" | "error" = "success") {
  message.value = text;
  tone.value = kind;
}

function formatPoints(value: number) {
  return value.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function computationHasData(computation: ScorecardComputation) {
  return computation.result.rows.some((row) => row.hasValue);
}

async function load() {
  loading.value = true;
  try {
    rows.value = await Promise.all(
      competencies(period.value).map(({ year: referenceYear, month }) =>
        api.get<ScorecardComputation>("/scorecard", { year: referenceYear, month }),
      ),
    );
  } catch (cause) {
    notify(cause instanceof Error ? cause.message : "Erro ao carregar scorecard.", "error");
  } finally {
    loading.value = false;
  }
}

async function loadDashboard() {
  dashboardLoading.value = true;
  dashboardError.value = "";
  try {
    dashboardData.value = await api.get<DashboardResponse>("/dashboard", periodToQuery(period.value));
  } catch (cause) {
    dashboardError.value = cause instanceof Error ? cause.message : "Erro ao carregar o Painel Executivo.";
  } finally {
    dashboardLoading.value = false;
  }
}

async function refresh() {
  await Promise.all([load(), loadDashboard()]);
  if (!dashboardError.value) lastSyncedAt.value = new Date();
}

async function recalculate() {
  busy.value = true;
  message.value = "";
  try {
    await refresh();
  } finally {
    busy.value = false;
  }
}

const current = computed(() =>
  rows.value.find((row) => row.year === period.value.endYear && row.month === period.value.endMonth) ?? null,
);
const presentMonths = computed(() => rows.value.filter(computationHasData));
const missingMonths = computed(() => rows.value.filter((row) => !computationHasData(row)));
const availableMonthsCount = computed(() => dashboardData.value?.monthKeys.length ?? presentMonths.value.length);
const pointsInPeriod = computed(() =>
  dashboardData.value?.pontosRealizados ?? rows.value.reduce((sum, row) => sum + row.result.totalPontos, 0),
);
const expectedPointsInPeriod = computed(() =>
  dashboardData.value?.pontuacaoPrevista ?? availableMonthsCount.value * SCORECARD_MONTHLY_POOL,
);
const cycleAttendance = computed(() => dashboardData.value?.atendimentoGeral ?? 0);
const currentPassCount = computed(() => current.value?.result.rows.filter((row) => row.pass).length ?? 0);
const coverageDescription = computed(() => {
  if (!presentMonths.value.length) return "0 meses com dados neste período.";
  const available = joinWithAnd(presentMonths.value.map((row) => MONTHS[row.month - 1] ?? String(row.month)));
  const missing = joinWithAnd(missingMonths.value.map((row) => MONTHS[row.month - 1] ?? String(row.month)));
  return `${presentMonths.value.length} de ${rows.value.length} meses com dados · Meses disponíveis: ${available}${missing ? ` · Faltam: ${missing}` : ""}`;
});

async function saveSnapshot() {
  if (!current.value) return;
  busy.value = true;
  message.value = "";
  try {
    await api.post("/scorecard", { year: current.value.year, month: current.value.month, overrides: {} });
    notify("Snapshot salvo com os valores publicados atuais.");
    await refresh();
  } catch (cause) {
    notify(cause instanceof Error ? cause.message : "Erro ao salvar snapshot.", "error");
  } finally {
    busy.value = false;
  }
}

async function persistPanelPeriod(nextYear: number, nextSemester: Semester) {
  try {
    await api.patch("/scorecard/panel-period", cycleFromYearSemester(nextYear, nextSemester));
    return true;
  } catch (cause) {
    notify(cause instanceof Error ? cause.message : "O período foi alterado, mas não foi possível salvá-lo.", "error");
    return false;
  }
}

function changePeriod(nextYear: number, nextSemester: Semester) {
  setPeriod(nextYear, nextSemester);
  void persistPanelPeriod(nextYear, nextSemester);
}

async function prepareNextSemester() {
  const next = nextWorkingPeriod(year.value, semester.value);
  setPeriod(next.year, next.semester);
  if (await persistPanelPeriod(next.year, next.semester)) {
    notify(`Período de trabalho preparado: ${next.year} ${next.semester} · Sem dados.`);
  }
}

async function clearHistory() {
  if (!confirm("Excluir os snapshots salvos deste ciclo? Os valores publicados dos módulos serão preservados.")) return;
  busy.value = true;
  message.value = "";
  try {
    const result = await api.delete<{ deleted: number }>("/scorecard/history", undefined, periodToQuery(period.value));
    notify(
      result.deleted
        ? `${result.deleted} snapshot(s) removido(s). Os valores publicados permanecem ao vivo.`
        : "Este ciclo não possui snapshots salvos para remover.",
    );
    await refresh();
  } catch (cause) {
    notify(cause instanceof Error ? cause.message : "Erro ao excluir histórico.", "error");
  } finally {
    busy.value = false;
  }
}

async function initialize() {
  try {
    const saved = await api.get<{ period: PeriodRange | null }>("/scorecard/panel-period");
    if (saved.period) {
      const savedCycle = yearSemesterFromCycle(saved.period);
      setPeriod(savedCycle.year, savedCycle.semester);
    }
  } catch {
    // O período operacional atual permanece como fallback, igual aos demais módulos.
  }
  initialized.value = true;
  await Promise.all([loadAvailablePeriods(), refresh()]);
}

function handleIndicatorDataChanged() {
  void refresh();
}

watch(period, () => {
  if (initialized.value) void refresh();
}, { deep: true, flush: "sync" });

onMounted(() => {
  void initialize();
  window.addEventListener(INDICATOR_DATA_CHANGED_EVENT, handleIndicatorDataChanged);
  refreshTimer = setInterval(() => {
    if (!document.hidden) void refresh();
  }, 30_000);
});
onBeforeUnmount(() => {
  window.removeEventListener(INDICATOR_DATA_CHANGED_EVENT, handleIndicatorDataChanged);
  if (refreshTimer) clearInterval(refreshTimer);
});
</script>

<template>
  <div class="scorecard-admin">
    <Card class="scorecard-admin-context">
      <div class="scorecard-admin-context-content">
        <div class="scorecard-admin-context-head">
          <div>
            <CardTitle class="text-base">Contexto de publicação</CardTitle>
            <CardDescription class="mt-1">
              Defina o período de trabalho e as ações aplicadas ao cálculo e ao snapshot do Scorecard.
            </CardDescription>
          </div>
          <div class="scorecard-admin-context-badges">
            <Badge variant="outline">{{ year }} {{ semester }}</Badge>
            <Badge :variant="presentMonths.length === rows.length && rows.length ? 'success' : 'outline'">
              {{ presentMonths.length }}/{{ rows.length || 6 }} meses
            </Badge>
          </div>
        </div>

        <PublicationPeriodField
          field-id="scorecard-period"
          :year="year"
          :semester="semester"
          :period-options="periodOptions"
          :available-periods="availablePeriods"
          :publish-period="period"
          @change="changePeriod"
          @prepare-next-semester="prepareNextSemester"
        >
          <p class="scorecard-admin-period-note">
            “Salvar snapshot” sempre usa o mês final deste período
            ({{ MONTHS[period.endMonth - 1] }}/{{ period.endYear }}). {{ coverageDescription }}
          </p>
        </PublicationPeriodField>

        <div class="scorecard-admin-actions">
          <Button variant="outline" size="sm" :disabled="busy" @click="recalculate">
            <RotateCw class="size-3.5" /> Recalcular
          </Button>
          <Button size="sm" :disabled="busy || !current" @click="saveSnapshot">
            <Save class="size-3.5" /> Salvar snapshot
          </Button>
          <Button
            v-if="canClear"
            class="scorecard-admin-clear"
            variant="destructive"
            size="sm"
            :disabled="busy"
            @click="clearHistory"
          >
            <Trash2 class="size-3.5" /> Limpar histórico do ciclo
          </Button>
        </div>
      </div>
    </Card>

    <div class="scorecard-admin-live" aria-live="polite">
      <span :class="{ 'is-syncing': busy }" />
      <template v-if="busy">Sincronizando…</template>
      <template v-else-if="lastSyncedAt">
        Ao vivo · atualizado às {{ lastSyncedAt.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }) }}
      </template>
      <template v-else>Ao vivo</template>
    </div>

    <div v-if="message" class="notice" :class="tone">{{ message }}</div>

    <div v-if="loading && !rows.length" class="loading-state"><div class="spinner" /></div>
    <div v-else class="scorecard-admin-metrics">
      <MetricCard
        class="scorecard-admin-metric is-accent"
        label="Pontos do mês"
        :value="formatPoints(current?.result.totalPontos ?? 0)"
        :detail="`de ${formatPoints(SCORECARD_MONTHLY_POOL)}`"
      />
      <MetricCard
        class="scorecard-admin-metric"
        label="Atendimento mensal"
        :value="`${(current?.result.atendimentoMes ?? 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`"
        :detail="`${currentPassCount} indicadores na meta`"
      />
      <MetricCard
        class="scorecard-admin-metric"
        label="Pontuação prevista — Semestre"
        :value="formatPoints(SCORECARD_MAX_POINTS)"
        detail="Meta total dos 6 meses"
      />
      <MetricCard
        class="scorecard-admin-metric"
        label="Pontuação prevista — Período"
        :value="formatPoints(expectedPointsInPeriod)"
        :detail="`Meta dos ${availableMonthsCount} mês(es) com dados`"
      />
      <MetricCard
        class="scorecard-admin-metric is-accent"
        label="Pontos no ciclo"
        :value="formatPoints(pointsInPeriod)"
        detail="Realizado acumulado no período"
      />
      <MetricCard
        class="scorecard-admin-metric"
        label="Atendimento do ciclo"
        :value="`${cycleAttendance.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`"
        :detail="`sobre ${formatPoints(expectedPointsInPeriod)} pontos do período`"
      />
      <MetricCard
        class="scorecard-admin-metric"
        label="Meses disponíveis"
        :value="String(availableMonthsCount)"
        :detail="`de ${rows.length || 6}`"
      />
    </div>

    <section class="scorecard-executive-card" aria-labelledby="scorecard-executive-title">
      <div v-if="dashboardLoading && !dashboardData" class="loading-state"><div class="spinner" /></div>
      <div v-else-if="dashboardError" class="error-state">
        <div><h3>Não foi possível carregar o Painel Executivo</h3><p>{{ dashboardError }}</p></div>
      </div>
      <div v-else-if="!dashboardData?.hasData" class="empty-state">
        <div><h3>Nenhum indicador publicado neste período</h3><p>As publicações dos módulos aparecerão aqui após serem concluídas.</p></div>
      </div>
      <ScorecardExecutivePanel
        v-else-if="dashboardData"
        :data="dashboardData"
        variant="admin"
        description="O farol usa a meta de cada indicador. Os valores vêm apenas do banco de dados: o publicado ao vivo pelo módulo de origem ou o último snapshot salvo."
        :indicator-routes="SCORECARD_INDICATOR_ROUTES"
      />
    </section>
  </div>
</template>
