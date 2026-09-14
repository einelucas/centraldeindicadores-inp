<script setup lang="ts">
import { Building2, Download, TrendingUp, Wrench, Zap } from "lucide-vue-next";
import type { PeriodRange, PublicationEnvelope } from "~/types/api";
import {
  periodQueryString,
  useReadingContextCycle,
} from "~/composables/useReadingContextCycle";
import { usePanelPdfExport } from "~/composables/usePanelPdfExport";
import { MONTHS, yearSemesterFromCycle } from "~/utils/period";
import { formatDate } from "~/utils/format";
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
const numberOrNull = (value: unknown): number | null =>
  typeof value === "number"
    ? value
    : value === null || value === undefined
      ? null
      : Number(value);

const isUnitSelected = computed(() => selectedUnit.value !== "all");
const result = computed(() =>
  Math.round(
    isUnitSelected.value
      ? numberValue(adminResult.value?.aderenciaGeral) * 100
      : numberValue(payload.value.resultado),
  ),
);
const meta = computed(() =>
  numberValue(payload.value.meta ?? publication.value?.target),
);
const displayedResult = computed(() => result.value);
const resultOk = computed(() => displayedResult.value >= meta.value);
const disciplineRows = computed(() =>
  isUnitSelected.value && Array.isArray(adminResult.value?.disciplineRows)
    ? (adminResult.value.disciplineRows as Array<Record<string, unknown>>)
    : [],
);
const disciplineResult = (name: string, publishedValue: unknown) => {
  if (!isUnitSelected.value) return numberOrNull(publishedValue);
  const row = disciplineRows.value.find((item) => item.disciplina === name);
  const adherence = numberOrNull(row?.aderencia);
  return adherence === null ? null : adherence * 100;
};
const civil = computed(() => disciplineResult("01 - Civil", payload.value.civil));
const mecanica = computed(() =>
  disciplineResult("02 - Mecânica", payload.value.mecanica),
);
const eletrica = computed(() =>
  disciplineResult("04 - Elétrica", payload.value.eletrica),
);
const selectedYear = computed(() =>
  isUnitSelected.value
    ? numberValue(adminResult.value?.selectedYear)
    : numberValue(
        payload.value.selectedYear,
        publication.value
          ? new Date(publication.value.publishedAt).getFullYear()
          : 0,
      ),
);
const selectedMonth = computed(() =>
  isUnitSelected.value
    ? numberValue(adminResult.value?.selectedMonth)
    : numberValue(payload.value.selectedMonth ?? payload.value.monthEnd, 12),
);
const documentosAtivos = computed(() =>
  numberValue(
    isUnitSelected.value
      ? adminResult.value?.activeDocuments
      : payload.value.documentosAtivos,
  ),
);

const monthly = computed(() => {
  const rows =
    isUnitSelected.value && Array.isArray(adminResult.value?.monthly)
      ? (adminResult.value.monthly as Array<Record<string, unknown>>)
      : Array.isArray(payload.value.mensal)
        ? (payload.value.mensal as Array<Record<string, unknown>>)
        : [];
  return rows
    .filter(
      (row) =>
        !isUnitSelected.value ||
        (numberValue(row.activeDocuments) > 0 && row.aderencia !== null),
    )
    .map((row) => ({
      label: String(row.label ?? ""),
      value: isUnitSelected.value
        ? numberOrNull(Number(row.aderencia) * 100)
        : numberOrNull(row.v),
    }));
});

const disciplineChartData = computed(() => {
  const rows = isUnitSelected.value
    ? disciplineRows.value
    : Array.isArray(payload.value.disciplinas)
      ? (payload.value.disciplinas as Array<Record<string, unknown>>)
      : [];
  return rows
    .filter((row) =>
      isUnitSelected.value
        ? row.aderencia !== null && row.aderencia !== undefined
        : row.v !== null && row.v !== undefined,
    )
    .map((row) => ({
      label: String(row.n ?? row.disciplina ?? "").replace(/^\d+\s*-\s*/, ""),
      value: isUnitSelected.value
        ? numberValue(row.aderencia) * 100
        : numberValue(row.v),
    }));
});

const units = computed(() => {
  const rows =
    isUnitSelected.value && Array.isArray(adminResult.value?.unitRows)
      ? (adminResult.value.unitRows as Array<Record<string, unknown>>)
      : Array.isArray(payload.value.unidades)
        ? (payload.value.unidades as Array<Record<string, unknown>>)
        : [];
  return rows
    .filter(
      (row) =>
        !isUnitSelected.value ||
        normalizeUnitCode(row.n ?? row.unit) === selectedUnit.value,
    )
    .filter((row) =>
      isUnitSelected.value
        ? row.aderencia !== null && row.aderencia !== undefined
        : row.v !== null && row.v !== undefined,
    )
    .map((row) => ({
      label: formatUnitLabel(String(row.n ?? row.unit ?? "")),
      sublabel: row.rsoNumero ? `RSO ${row.rsoNumero}` : undefined,
      value: numberValue(row.v ?? Number(row.aderencia ?? 0) * 100),
    }));
});
const availableUnits = computed(() => {
  const rows = Array.isArray(payload.value.unidades)
    ? (payload.value.unidades as Array<Record<string, unknown>>)
    : [];
  return rows.map((row) => String(row.n ?? ""));
});

function disciplineValue(value: number | null): string {
  return value === null ? "—" : `${Math.round(value)}%`;
}
function competenceLabel(year: number, month: number): string {
  return `${MONTHS[month - 1] ?? month}/${year}`;
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const body = await api.get<PublicationEnvelope>(
      "/publicacoes/idp",
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
    const body = await api.get<{ result: Record<string, unknown> }>("/idp", {
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
  await exportPdf(`IDP_painel_${new Date().toISOString().slice(0, 10)}.pdf`);
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
          <h2>Aderência do Cronograma (IDP)</h2>
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
        <div class="mgrid">
          <div :class="['mc', resultOk ? 'G' : 'R']">
            <div class="mc-head">
              <div class="ml">Execução geral</div>
              <div class="mc-icon"><TrendingUp :size="16" /></div>
            </div>
            <div :class="['mv', resultOk ? 'G' : 'R']">
              {{ displayedResult }}%
            </div>
            <div class="mm">Meta &gt;{{ meta }}%</div>
            <div :class="['ms', resultOk ? 'ok' : 'no']">
              {{ resultOk ? "✓ Atingida" : "✗ Abaixo" }}
            </div>
          </div>

          <div :class="['mc', civil !== null && civil >= meta ? 'G' : 'A']">
            <div class="mc-head">
              <div class="ml">Civil</div>
              <div class="mc-icon"><Building2 :size="16" /></div>
            </div>
            <div :class="['mv', civil !== null && civil >= meta ? 'G' : 'A']">
              {{ disciplineValue(civil) }}
            </div>
            <div class="mm">Por disciplina</div>
          </div>

          <div
            :class="['mc', mecanica !== null && mecanica >= meta ? 'G' : 'A']"
          >
            <div class="mc-head">
              <div class="ml">Mecânica</div>
              <div class="mc-icon"><Wrench :size="16" /></div>
            </div>
            <div
              :class="['mv', mecanica !== null && mecanica >= meta ? 'G' : 'A']"
            >
              {{ disciplineValue(mecanica) }}
            </div>
            <div class="mm">Por disciplina</div>
          </div>

          <div
            :class="['mc', eletrica !== null && eletrica >= meta ? 'G' : 'A']"
          >
            <div class="mc-head">
              <div class="ml">Elétrica</div>
              <div class="mc-icon"><Zap :size="16" /></div>
            </div>
            <div
              :class="['mv', eletrica !== null && eletrica >= meta ? 'G' : 'A']"
            >
              {{ disciplineValue(eletrica) }}
            </div>
            <div class="mm">Por disciplina</div>
          </div>
        </div>

        <div class="card indicator-card">
          <div class="ph">Aderência do Cronograma — Avanço Físico (RSO)</div>

          <p class="ps rdo-panel-summary">
            <span class="rdo-panel-target">META: &gt;{{ meta }}%</span>
            <span>
              Resultado:
              <strong
                :style="{
                  color: resultOk ? '#609346' : '#cc5121',
                  fontSize: '14px',
                }"
                >{{ displayedResult }}%</strong
              >
            </span>
            <span style="color: #bbb">
              — competência {{ competenceLabel(selectedYear, selectedMonth) }} ·
              {{ documentosAtivos }} RSO(s) ativo(s) · publicado em
              {{ formatDate(publication.publishedAt, true) }} por
              {{ publication.publishedBy?.name ?? "sistema" }} · versão
              {{ publication.version }}
            </span>
          </p>

          <div class="g2 indicator-subgrid">
            <div class="indicator-subcard">
              <div class="ct">Aderência mensal (%)</div>
              <div class="cs">
                Comparativo do percentual executado com a meta em cada mês.
              </div>
              <LineChart
                v-if="monthly.length"
                :points="monthly"
                :target="meta"
                suffix="%"
                color="#304f7e"
                series-label="Aderência"
              />
              <p v-else class="ps">Sem dados mensais publicados.</p>
            </div>

            <div v-if="disciplineChartData.length" class="indicator-subcard">
              <div class="ct">Aderência por disciplina (%)</div>
              <div class="cs">
                Comparativo do percentual executado por disciplina.
              </div>
              <BarChart
                :points="disciplineChartData"
                :target="meta"
                suffix="%"
                color="#304f7e"
              />
            </div>
          </div>

          <div class="indicator-subcard">
            <div class="ct">Execução por unidade — RSO utilizado</div>
            <div class="cs">Leitura visual de desempenho por unidade.</div>
            <UnitProgressBars
              :items="units"
              :target="meta"
              suffix="%"
              empty-message="Sem unidades publicadas."
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
