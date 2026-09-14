<script setup lang="ts">
import {
  CheckCircle2,
  Download,
  FileText,
  Hourglass,
  PencilLine,
} from "lucide-vue-next";

import type { PeriodRange, PublicationEnvelope } from "~/types/api";

import {
  periodQueryString,
  useReadingContextCycle,
} from "~/composables/useReadingContextCycle";

import { usePanelPdfExport } from "~/composables/usePanelPdfExport";

import { yearSemesterFromCycle } from "~/utils/period";

import { formatDate, formatNumber } from "~/utils/format";
import { formatUnitLabel, normalizeUnitCode } from "~/logic/lib/units";
import { INDICATOR_DATA_CHANGED_EVENT } from "~/utils/browser-events";

const api = useApi();

const publication = ref<PublicationEnvelope["publication"]>(null);
const adminResult = ref<Record<string, unknown> | null>(null);
const loading = ref(true);
const unitLoading = ref(false);
const error = ref("");
const unitError = ref("");
const selectedUnit = ref("all");
let unitRequestId = 0;

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

const isUnitSelected = computed(() => selectedUnit.value !== "all");
const emitted = computed(() =>
  numberValue(
    isUnitSelected.value
      ? adminResult.value?.totalEmitidos
      : payload.value.emitidos,
  ),
);
const approved = computed(() =>
  numberValue(
    isUnitSelected.value
      ? adminResult.value?.totalAprovados
      : payload.value.aprovados,
  ),
);
const reviewingCount = computed(() =>
  numberValue(
    isUnitSelected.value ? adminResult.value?.totalRevisar : 0,
  ),
);
const fillingCount = computed(() =>
  numberValue(
    isUnitSelected.value ? adminResult.value?.totalPreenchendo : 0,
  ),
);
const percentOfEmitted = (count: number) =>
  emitted.value > 0 ? (count / emitted.value) * 100 : 0;
const result = computed(() =>
  Math.round(
    isUnitSelected.value
      ? percentOfEmitted(approved.value)
      : numberValue(payload.value.resultado),
  ),
);

const meta = computed(() =>
  numberValue(payload.value.meta ?? publication.value?.target),
);

const reviewing = computed(() =>
  isUnitSelected.value
    ? percentOfEmitted(reviewingCount.value)
    : numberValue(payload.value.emRevisaoPct),
);

const filling = computed(() =>
  isUnitSelected.value
    ? percentOfEmitted(fillingCount.value)
    : numberValue(payload.value.preenchendoPct),
);

const resultOk = computed(() => displayedResult.value >= meta.value);

const displayedReviewingCount = computed(() =>
  isUnitSelected.value
    ? reviewingCount.value
    : Math.round((reviewing.value / 100) * emitted.value),
);

const displayedFillingCount = computed(() =>
  isUnitSelected.value
    ? fillingCount.value
    : Math.round((filling.value / 100) * emitted.value),
);

const monthly = computed(() => {
  const rows =
    isUnitSelected.value && Array.isArray(adminResult.value?.months)
      ? (adminResult.value.months as Array<Record<string, unknown>>)
      : Array.isArray(payload.value.mensal)
        ? (payload.value.mensal as Array<Record<string, unknown>>)
        : [];

  return rows
    .map((row) => ({
      label: String(row.label ?? ""),
      value: numberValue(row.v ?? Number(row.aderencia ?? 0) * 100, Number.NaN),
    }))
    .filter((row) => Number.isFinite(row.value));
});
const availableUnits = computed(() => {
  const rows = Array.isArray(payload.value.unidades)
    ? (payload.value.unidades as Array<Record<string, unknown>>)
    : [];
  return rows.map((row) => String(row.n ?? row.name ?? ""));
});
const displayedResult = computed(() => result.value);

const units = computed(() => {
  const rows =
    isUnitSelected.value && Array.isArray(adminResult.value?.units)
      ? (adminResult.value.units as Array<Record<string, unknown>>)
      : Array.isArray(payload.value.unidades)
        ? (payload.value.unidades as Array<Record<string, unknown>>)
        : [];

  return rows
    .filter(
      (row) =>
        !isUnitSelected.value ||
        normalizeUnitCode(row.n ?? row.name) === selectedUnit.value,
    )
    .map((row) => ({
      // `formatUnitLabel` é idempotente em nomes já formatados — cobre
      // também publicações antigas cujo payload salvo ainda guarda a sigla.
      label: formatUnitLabel(String(row.n ?? row.name ?? "")),
      value: numberValue(row.v ?? Number(row.aderencia ?? 0) * 100, Number.NaN),
    }))
    .filter((row) => Number.isFinite(row.value));
});

const statusItems = computed(() => [
  {
    label: "Aprovado",
    value: displayedResult.value,
    color: "#609346",
  },
  {
    label: "Em revisão",
    value: Math.round(reviewing.value),
    color: "#eaa239",
  },
  {
    label: "Preenchendo",
    value: Math.round(filling.value),
    color: "#2e6db4",
  },
]);

async function load() {
  loading.value = true;
  error.value = "";

  try {
    const body = await api.get<PublicationEnvelope>(
      "/publicacoes/rdo",
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
  const requestId = ++unitRequestId;
  if (!isUnitSelected.value) {
    adminResult.value = null;
    unitLoading.value = false;
    unitError.value = "";
    return;
  }
  adminResult.value = null;
  unitLoading.value = true;
  unitError.value = "";
  try {
    const body = await api.get<{ result: Record<string, unknown> }>("/rdo", {
      ...Object.fromEntries(
        new URLSearchParams(periodQueryString(cycle.value)),
      ),
      unidade: formatUnitLabel(selectedUnit.value),
    });
    if (requestId === unitRequestId) adminResult.value = body.result;
  } catch (cause) {
    if (requestId === unitRequestId) {
      adminResult.value = null;
      unitError.value =
        cause instanceof Error
          ? cause.message
          : "Falha ao carregar os dados da unidade.";
    }
  } finally {
    if (requestId === unitRequestId) unitLoading.value = false;
  }
}

async function handleExportPdf() {
  await exportPdf(`RDO_painel_${new Date().toISOString().slice(0, 10)}.pdf`);
}

async function refresh() {
  await load();
  await loadUnitData();
}

watch(cycle, refresh, { deep: true });
watch(selectedUnit, () => {
  void loadUnitData();
});

onMounted(() => {
  void refresh();

  window.addEventListener(INDICATOR_DATA_CHANGED_EVENT, refresh);
});

onBeforeUnmount(() => {
  window.removeEventListener(INDICATOR_DATA_CHANGED_EVENT, refresh);
});
</script>

<template>
  <div class="stack painel-frontend">
    <div ref="panelRef" class="surface">
      <div class="surface-header">
        <div>
          <h2>Aprovação de RDO</h2>
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

      <div v-else-if="unitLoading" class="loading-state">
        <div class="spinner" />
      </div>

      <div v-else-if="unitError" class="error-state">
        <div>
          <h3>Não foi possível carregar a unidade</h3>
          <p>{{ unitError }}</p>
          <button class="btn mt-3" type="button" @click="loadUnitData">
            Tentar novamente
          </button>
        </div>
      </div>

      <div v-else class="surface-body">
        <!-- Cards superiores -->
        <div class="mgrid">
          <div class="mc G">
            <div class="mc-head">
              <div class="ml">Resultado</div>

              <div class="mc-icon">
                <CheckCircle2 :size="16" />
              </div>
            </div>

            <div class="mv G">{{ displayedResult }}%</div>

            <div class="mm">Meta &gt;{{ meta }}%</div>

            <div :class="['ms', resultOk ? 'ok' : 'no']">
              {{ resultOk ? "✓ Atingida" : "✗ Abaixo" }}
            </div>
          </div>

          <div class="mc G">
            <div class="mc-head">
              <div class="ml">Relatórios aprovados</div>

              <div class="mc-icon">
                <FileText :size="16" />
              </div>
            </div>

            <div class="mv G">
              {{ formatNumber(approved) }}
            </div>

            <div class="mm">
              De
              {{ formatNumber(emitted) }}
              emitidos
            </div>
          </div>

          <div class="mc A">
            <div class="mc-head">
              <div class="ml">Em revisão</div>

              <div class="mc-icon">
                <Hourglass :size="16" />
              </div>
            </div>

            <div class="mv A">{{ reviewing.toFixed(1) }}%</div>

            <div class="mm">
              {{ formatNumber(displayedReviewingCount) }}
              relatórios
            </div>
          </div>

          <div class="mc A">
            <div class="mc-head">
              <div class="ml">Preenchendo</div>

              <div class="mc-icon">
                <PencilLine :size="16" />
              </div>
            </div>

            <div class="mv A">{{ filling.toFixed(1) }}%</div>

            <div class="mm">
              {{ formatNumber(displayedFillingCount) }}
              relatórios
            </div>
          </div>
        </div>

        <!-- Painel -->
        <div class="card indicator-card">
          <div class="ph">Aprovação de RDO</div>

          <p class="ps rdo-panel-summary">
            <span class="rdo-panel-target"> META: &gt;{{ meta }}% </span>

            <span>
              Resultado:

              <strong
                :style="{
                  color: resultOk ? '#609346' : '#cc5121',
                  fontSize: '14px',
                }"
              >
                {{ displayedResult }}%
              </strong>
            </span>

            <span style="color: #bbb">
              — publicado em
              {{ formatDate(publication.publishedAt, true) }}
              por
              {{ publication.publishedBy?.name ?? "sistema" }}
            </span>
          </p>

          <!-- Gráficos principais -->
          <div class="g2 indicator-subgrid">
            <!-- Donut -->
            <div class="indicator-subcard">
              <div class="ct">Distribuição de status</div>

              <div class="cs">
                Proporção entre relatórios aprovados, em revisão e preenchendo.
              </div>

              <!--
                O DonutChart controla internamente
                tamanho, altura, legenda e responsividade.
              -->
              <DonutChart :items="statusItems" />
            </div>

            <!-- Gráfico mensal -->
            <div class="indicator-subcard">
              <div class="ct">Aprovação mensal</div>

              <div class="cs">
                Aderência mensal comparada com a meta do indicador.
              </div>

              <LineChart
                :points="monthly"
                :target="meta"
                suffix="%"
                color="#304f7e"
                series-label="Aprovação"
              />
            </div>
          </div>

          <!-- Aprovação por unidade -->
          <div class="indicator-subcard">
            <div class="ct">Aprovação por unidade</div>

            <div class="cs">Leitura visual de desempenho por unidade.</div>

            <UnitProgressBars :items="units" :target="meta" suffix="%" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
