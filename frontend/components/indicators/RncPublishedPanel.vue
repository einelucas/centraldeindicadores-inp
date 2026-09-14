<script setup lang="ts">
import { CalendarDays, Download, Timer } from "lucide-vue-next";
import type { PeriodRange, PublicationEnvelope } from "~/types/api";
import {
  periodQueryString,
  useReadingContextCycle,
} from "~/composables/useReadingContextCycle";
import { usePanelPdfExport } from "~/composables/usePanelPdfExport";
import { yearSemesterFromCycle } from "~/utils/period";
import { formatDate, formatNumber } from "~/utils/format";
import { formatRncUnitLabel } from "~/logic/features/rnc/utils/units";
import { normalizeUnitCode } from "~/logic/lib/units";
import { INDICATOR_DATA_CHANGED_EVENT } from "~/utils/browser-events";

const api = useApi();
const publication = ref<PublicationEnvelope["publication"]>(null);
const adminResult = ref<Record<string, unknown> | null>(null);
const loading = ref(true);
const error = ref("");
const selectedUnit = ref("all");
const { cycle, setPeriod } = useReadingContextCycle();
const period = computed<PeriodRange>({
  get: () => cycle.value,
  set: (range) => {
    const { year, semester } = yearSemesterFromCycle(range);
    setPeriod(year, semester);
  },
});
const panelRef = ref<HTMLElement | null>(null);
const {
  exporting,
  error: exportError,
  exportPdf,
} = usePanelPdfExport(panelRef);
const payload = computed<Record<string, unknown>>(
  () => publication.value?.payload ?? {},
);
const numberValue = (value: unknown, fallback = 0) =>
  typeof value === "number" ? value : Number(value ?? fallback);

const result = computed(() =>
  numberValue(adminResult.value?.resultadoDias ?? payload.value.resultado),
);
const meta = computed(() =>
  numberValue(
    adminResult.value?.metaDias ??
      payload.value.meta ??
      publication.value?.target,
    15,
  ),
);
const resolved = computed(() =>
  numberValue(
    adminResult.value?.totalTratadas ?? payload.value.semestreResolvidas,
  ),
);
const total = computed(() =>
  numberValue(adminResult.value?.totalCriadas ?? payload.value.semestreTotal),
);
const semesterPercent = computed(() =>
  total.value ? Math.round((resolved.value / total.value) * 100) : 0,
);
const displayedResult = computed(() =>
  selectedUnit.value === "all"
    ? result.value
    : (units.value[0]?.value ?? result.value),
);
const resultOk = computed(() => displayedResult.value <= meta.value);
const monthly = computed(() => {
  const rows =
    selectedUnit.value !== "all" && Array.isArray(adminResult.value?.months)
      ? (adminResult.value.months as Array<Record<string, unknown>>)
      : Array.isArray(payload.value.mensal)
        ? (payload.value.mensal as Array<Record<string, unknown>>)
        : [];
  return rows
    .map((row) => ({
      label: String(row.label ?? ""),
      value: numberValue(row.v ?? row.diasMedios, Number.NaN),
    }))
    .filter((row) => Number.isFinite(row.value));
});
const offenders = computed(() => {
  const colors = ["#304f7e", "#eaa239", "#609346", "#bdbfc1", "#7b5ea7"];
  const rows =
    selectedUnit.value !== "all" && Array.isArray(adminResult.value?.ofensores)
      ? (adminResult.value.ofensores as Array<Record<string, unknown>>)
      : Array.isArray(payload.value.ofensores)
        ? (payload.value.ofensores as Array<Record<string, unknown>>)
        : [];
  return rows.map((row, index) => ({
    label: String(row.n ?? ""),
    value: numberValue(row.pct),
    color: colors[index % colors.length] ?? "#304f7e",
  }));
});
const units = computed(() => {
  const rows =
    selectedUnit.value !== "all" && Array.isArray(adminResult.value?.units)
      ? (adminResult.value.units as Array<Record<string, unknown>>)
      : Array.isArray(payload.value.unidades)
        ? (payload.value.unidades as Array<Record<string, unknown>>)
        : [];
  return rows
    .filter(
      (row) =>
        selectedUnit.value === "all" ||
        normalizeUnitCode(row.n) === selectedUnit.value,
    )
    .map((row) => ({
      label: formatRncUnitLabel(String(row.n ?? row.name ?? "")),
      value: numberValue(row.v ?? Number(row.aderencia ?? 0) * 100),
    }));
});
const availableUnits = computed(() => {
  const rows = Array.isArray(payload.value.unidades)
    ? (payload.value.unidades as Array<Record<string, unknown>>)
    : [];
  return rows.map((row) => String(row.n ?? ""));
});

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const body = await api.get<PublicationEnvelope>(
      "/publicacoes/rnc",
      Object.fromEntries(new URLSearchParams(periodQueryString(cycle.value))),
    );
    publication.value = body.publication;
  } catch (cause) {
    error.value =
      cause instanceof Error
        ? cause.message
        : "Falha ao carregar o painel publicado.";
  } finally {
    loading.value = false;
  }
}

async function loadUnitData() {
  if (selectedUnit.value === "all") {
    adminResult.value = null;
    return;
  }
  try {
    const body = await api.get<{ result: Record<string, unknown> }>("/rnc", {
      ...Object.fromEntries(
        new URLSearchParams(periodQueryString(cycle.value)),
      ),
      meta: meta.value,
      unidade: formatRncUnitLabel(selectedUnit.value),
    });
    adminResult.value = body.result;
  } catch {
    adminResult.value = null;
  }
}

async function handleExportPdf() {
  await exportPdf(`RNC_painel_${new Date().toISOString().slice(0, 10)}.pdf`);
}

watch(
  cycle,
  () => {
    void load();
    void loadUnitData();
  },
  { deep: true },
);
watch(selectedUnit, () => {
  void loadUnitData();
});
onMounted(() => {
  void load();
  window.addEventListener(INDICATOR_DATA_CHANGED_EVENT, load);
  window.addEventListener("rnc:published", load);
});
onBeforeUnmount(() => {
  window.removeEventListener(INDICATOR_DATA_CHANGED_EVENT, load);
  window.removeEventListener("rnc:published", load);
});
</script>

<template>
  <div class="stack painel-frontend">
    <div ref="panelRef" class="surface">
      <div class="surface-header">
        <div>
          <h2>RNC — Tempo para Resolução</h2>
          <p v-if="publication">
            Publicação v{{ publication.version }} ·
            {{ formatDate(publication.publishedAt, true) }}
          </p>
        </div>
        <div class="toolbar">
          <PeriodSelector v-model="period" />
          <UnitSelector v-model="selectedUnit" :units="availableUnits" />
          <button
            type="button"
            class="btn btn-icon"
            title="PDF"
            :disabled="!publication || exporting"
            @click="handleExportPdf"
          >
            <Download :size="16" />
          </button>
        </div>
      </div>

      <p v-if="exportError" class="ps px-5" style="color: #cc5121">
        {{ exportError }}
      </p>
      <div v-if="loading && !publication" class="loading-state">
        <div class="spinner" />
      </div>
      <div v-else-if="error && !publication" class="error-state">
        <div>
          <h3>Não foi possível carregar o painel</h3>
          <p>{{ error }}</p>
        </div>
      </div>
      <div v-else-if="!publication" class="empty-state">
        <div>
          <h3>Nenhuma publicação para este período</h3>
          <p>
            Escolha outro ano ou semestre acima, ou publique os dados na área de
            Administração.
          </p>
        </div>
      </div>

      <div v-else class="surface-body">
        <div class="mgrid">
          <div :class="['mc', resultOk ? 'G' : 'R']">
            <div class="mc-head">
              <div class="ml">Resultado</div>
              <div class="mc-icon"><Timer :size="16" /></div>
            </div>
            <div :class="['mv', resultOk ? 'G' : 'R']">
              {{ Math.round(displayedResult) }} dias
            </div>
            <div class="mm">Meta ≤{{ meta }} dias</div>
            <div :class="['ms', resultOk ? 'ok' : 'no']">
              {{ resultOk ? "✓ Atingida" : "✕ Fora da meta" }}
            </div>
          </div>
          <div class="mc G">
            <div class="mc-head">
              <div class="ml">Semestre</div>
              <div class="mc-icon"><CalendarDays :size="16" /></div>
            </div>
            <div class="mv G">{{ semesterPercent }}%</div>
            <div class="mm">
              {{ formatNumber(resolved) }}/{{ formatNumber(total) }} tratadas
            </div>
            <div class="ms ok" style="visibility: hidden" aria-hidden="true">
              —
            </div>
          </div>
        </div>

        <div class="card indicator-card">
          <div class="ph">RNC — Tempo para Resolução</div>
          <p class="ps rdo-panel-summary">
            <span class="rdo-panel-target">META: ≤{{ meta }} dias</span>
            <span
              >Resultado:
              <strong
                :style="{
                  color: resultOk ? '#609346' : '#cc5121',
                  fontSize: '14px',
                }"
                >{{ Math.round(displayedResult) }} dias</strong
              ></span
            >
            <span style="color: #bbb"
              >— quanto menor, melhor — publicado em
              {{ formatDate(publication.publishedAt, true) }} por
              {{ publication.publishedBy?.name ?? "sistema" }}</span
            >
          </p>
          <p class="ps" style="margin: -4px 0 12px">
            Prazo médio consolidado pela média simples dos resultados mensais do
            período selecionado.
          </p>

          <div class="g2 indicator-subgrid">
            <div class="indicator-subcard">
              <div class="ct">Tempo médio por mês (dias)</div>
              <div class="cs">
                Comparativo do tempo médio com a meta em dias.
              </div>
              <LineChart
                :points="monthly"
                :target="meta"
                suffix=" dias"
                color="#304f7e"
                series-label="Tempo médio"
              />
            </div>
            <div class="indicator-subcard">
              <div class="ct">Origem das não conformidades</div>
              <div class="cs">Distribuição percentual por origem.</div>
              <DonutChart :items="offenders" />
            </div>
          </div>

          <div class="indicator-subcard">
            <div class="ct">Aderência de tratativa por unidade</div>
            <div class="cs">Leitura visual de desempenho por unidade.</div>
            <UnitProgressBars :items="units" :target="80" suffix="%" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
