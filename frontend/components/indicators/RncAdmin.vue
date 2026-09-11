<script setup lang="ts">
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  FileDown,
  FileSpreadsheet,
  Loader2,
  RotateCw,
  Send,
  Sparkles,
  Trash2,
  UploadCloud,
} from "lucide-vue-next";
import type { PeriodRange, PublicationEnvelope, UploadImportResult } from "~/types/api";
import type { RncResult } from "~/logic/features/rnc/types";
import { RNC_DEFAULT_MAX_DIAS } from "~/logic/features/rnc/types";
import { exportRncPdf } from "~/logic/features/rnc/exports/pdf";
import { formatRncUnitLabel, normalizeRncUnitCode } from "~/logic/features/rnc/utils/units";
import { notifyIndicatorDataChanged } from "~/utils/browser-events";
import { MONTHS, periodToQuery } from "~/utils/period";
import { formatDate, formatNumber, formatPercent } from "~/utils/format";

interface RncResponse {
  total: number;
  metaDias: number;
  result: RncResult;
  lastImport: null | {
    id: string;
    fileName: string;
    completedAt: string | null;
    totalFound: number;
    totalInserted: number;
    totalUpdated: number;
    totalIgnored: number;
    totalRejected: number;
  };
}

defineProps<{ canPublish: boolean; canClear: boolean }>();

const api = useApi();
const upload = useFileUpload();
const { year, semester, cycle, setPeriod } = useReadingContextCycle();
const { availablePeriods, periodOptions, loadAvailablePeriods } = usePublicationPeriodOptions("rnc", year, semester);

const viewFilter = ref<PeriodRange | null | undefined>(undefined);
const queryPeriod = computed(() => viewFilter.value !== undefined ? viewFilter.value : cycle.value);
const metaDias = ref(RNC_DEFAULT_MAX_DIAS);
const data = ref<RncResponse | null>(null);
const coverage = ref<RncResult | null>(null);
const publication = ref<PublicationEnvelope["publication"]>(null);
const loading = ref(true);
const busy = ref(false);
const message = ref("");
const messageTone = ref<"success" | "error" | "">("");

const dragging = ref(false);
const uploading = ref(false);
const uploadingFileCount = ref(0);
const uploadResult = ref<UploadImportResult | null>(null);
const resultModal = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);

const excludedUnits = ref<string[]>([]);
const unitDialogOpen = ref(false);
const clearModalOpen = ref(false);
const clearPeriodRange = ref<PeriodRange | null>(null);
const justificationOpen = ref(false);

const selectedMonth = ref("");
const unitFilter = ref("all");
const monthFilter = ref("all");
const yearFilter = ref("all");

const result = computed(() => data.value?.result ?? null);
const months = computed(() => result.value?.months ?? []);
const units = computed(() => result.value?.units ?? []);
const offenders = computed(() => result.value?.ofensores ?? []);
const selectedMonthResult = computed(() =>
  months.value.find((month) => `${month.year}-${String(month.month + 1).padStart(2, "0")}` === selectedMonth.value) ?? null,
);
const filteredUnits = computed(() =>
  unitFilter.value === "all" ? units.value : units.value.filter((unit) => unit.name === unitFilter.value),
);
const filteredMonths = computed(() => months.value.filter((month) =>
  (yearFilter.value === "all" || month.year === Number(yearFilter.value)) &&
  (monthFilter.value === "all" || month.month + 1 === Number(monthFilter.value)),
));
const availableYears = computed(() =>
  Array.from(new Set(months.value.map((month) => month.year))).sort((a, b) => b - a),
);
const availableMonths = computed(() =>
  Array.from(new Set(months.value.map((month) => month.month + 1))).sort((a, b) => a - b),
);
const coverageMonths = computed(() => (viewFilter.value === undefined ? months.value : coverage.value?.months ?? []));
const monthsWithData = computed(() => Math.min(6, coverageMonths.value.length));
const isPublished = computed(() => Boolean(
  publication.value && publication.value.cycleYear === year.value && publication.value.cycleSemester === semester.value,
));
const unitOptions = computed(() => units.value.map((unit) => ({
  code: normalizeRncUnitCode(unit.name),
  label: formatRncUnitLabel(unit.name),
})));
const justificationYear = computed(() => cycle.value.endYear);
const justificationMonth = computed(() => cycle.value.endMonth);

function showMessage(text: string, tone: "success" | "error" = "success") {
  message.value = text;
  messageTone.value = tone;
}

function selectLatestMonth() {
  const keys = months.value.map((month) => `${month.year}-${String(month.month + 1).padStart(2, "0")}`);
  if (!keys.includes(selectedMonth.value)) selectedMonth.value = keys.at(-1) ?? "";
}

async function load() {
  loading.value = true;
  message.value = "";
  try {
    data.value = await api.get<RncResponse>("/rnc", { ...periodToQuery(queryPeriod.value), meta: metaDias.value });
    metaDias.value = data.value.metaDias;
    excludedUnits.value = data.value.result.excludedUnits;
    selectLatestMonth();
  } catch (cause) {
    showMessage(cause instanceof Error ? cause.message : "Erro ao carregar dados do RNC.", "error");
  } finally {
    loading.value = false;
  }
}

async function loadCoverage() {
  if (viewFilter.value === undefined) {
    coverage.value = null;
    return;
  }
  try {
    const body = await api.get<RncResponse>("/rnc", { ...periodToQuery(cycle.value), meta: metaDias.value });
    coverage.value = body.result;
  } catch {
    coverage.value = null;
  }
}

async function loadPublication() {
  try {
    const body = await api.get<PublicationEnvelope>("/publicacoes/rnc", periodToQuery(cycle.value));
    publication.value = body.publication;
  } catch {
    publication.value = null;
  }
}

function onDragOver(event: DragEvent) {
  event.preventDefault();
  dragging.value = true;
}
function onDragLeave() { dragging.value = false; }
async function onDrop(event: DragEvent) {
  event.preventDefault();
  dragging.value = false;
  const files = Array.from(event.dataTransfer?.files ?? []);
  if (files.length) await handleFiles(files);
}
function onFileInputChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files ?? []);
  if (files.length) void handleFiles(files);
}

async function handleFiles(files: File[]) {
  uploading.value = true;
  uploadingFileCount.value = files.length;
  message.value = "";
  try {
    const outcome = await upload.uploadFiles("rnc", files);
    uploadResult.value = outcome;
    resultModal.value = true;
    showMessage(
      `Importação concluída: ${outcome.totals.inserted} inseridos, ${outcome.totals.updated} atualizados, ` +
      `${outcome.totals.ignored} ignorados e ${outcome.totals.rejected} rejeitados.`,
    );
    await Promise.all([load(), loadCoverage(), loadAvailablePeriods(), loadPublication()]);
  } catch (cause) {
    showMessage(cause instanceof Error ? cause.message : "Erro durante a importação do RNC.", "error");
  } finally {
    uploading.value = false;
    uploadingFileCount.value = 0;
    if (fileInput.value) fileInput.value.value = "";
  }
}

async function saveExcludedUnits(next: string[]) {
  busy.value = true;
  try {
    await api.patch("/rnc", { excludedUnits: next });
    excludedUnits.value = next;
    unitDialogOpen.value = false;
    showMessage("Unidades atualizadas e indicador recalculado.");
    await Promise.all([load(), loadCoverage()]);
  } catch (cause) {
    showMessage(cause instanceof Error ? cause.message : "Erro ao salvar unidades ignoradas.", "error");
  } finally {
    busy.value = false;
  }
}

function openClearModal() {
  clearPeriodRange.value = null;
  clearModalOpen.value = true;
}
async function fetchAffectedCount(period: PeriodRange | null): Promise<number> {
  const body = await api.get<{ count: number }>("/rnc/registros", period ? periodToQuery(period) : {});
  return body.count;
}
async function confirmClear() {
  busy.value = true;
  try {
    await api.delete("/rnc/registros", clearPeriodRange.value ? periodToQuery(clearPeriodRange.value) : { all: true });
    clearModalOpen.value = false;
    showMessage("Registros excluídos. A publicação vigente foi preservada.");
    await Promise.all([load(), loadCoverage(), loadAvailablePeriods()]);
  } catch (cause) {
    showMessage(cause instanceof Error ? cause.message : "Erro ao excluir registros.", "error");
  } finally {
    busy.value = false;
  }
}

async function publish() {
  busy.value = true;
  try {
    await api.post("/publicacoes/rnc", { ...periodToQuery(cycle.value), metaDias: metaDias.value });
    showMessage("Painel RNC publicado com sucesso.");
    notifyIndicatorDataChanged();
    window.dispatchEvent(new Event("rnc:published"));
    await loadPublication();
  } catch (cause) {
    showMessage(cause instanceof Error ? cause.message : "Erro ao publicar o painel RNC.", "error");
  } finally {
    busy.value = false;
  }
}

function exportPdf() {
  if (result.value) exportRncPdf(result.value);
}

watch(queryPeriod, () => void load(), { deep: true });
watch(cycle, () => { void loadPublication(); void loadCoverage(); }, { deep: true });
watch(metaDias, () => { void load(); void loadCoverage(); });
onMounted(() => { void load(); void loadPublication(); });
</script>

<template>
  <div class="rdo-admin-panel surface">
    <div class="rdo-admin-body">
      <div
        class="rdo-upload-zone"
        :class="{ 'rdo-upload-zone--dragging': dragging, 'rdo-upload-zone--busy': uploading }"
        role="button"
        tabindex="0"
        aria-live="polite"
        @dragover="onDragOver"
        @dragleave="onDragLeave"
        @drop="onDrop"
        @keydown.enter="fileInput?.click()"
      >
        <label class="rdo-upload-label">
          <span class="rdo-upload-icon">
            <Loader2 v-if="uploading" :size="21" class="animate-spin" />
            <UploadCloud v-else :size="21" />
          </span>
          <strong>{{ uploading ? "Enviando e processando arquivos…" : "Importar registros de não conformidade" }}</strong>
          <small v-if="uploading">
            {{ uploadingFileCount === 1 ? "1 arquivo" : `${uploadingFileCount} arquivos` }} — aguarde o processamento no servidor.
          </small>
          <small v-else>Arraste os arquivos aqui ou clique para selecionar planilhas Excel/CSV do RNC.</small>
          <input ref="fileInput" type="file" hidden multiple accept=".xlsx,.xls,.xlsm,.xlsb,.xltx,.xlt,.csv" :disabled="uploading" @change="onFileInputChange" />
        </label>
      </div>

      <div v-if="message" class="notice" :class="messageTone">{{ message }}</div>

      <section class="rdo-admin-context">
        <div class="rdo-admin-context-head">
          <div><h3>Contexto de publicação</h3><p>Período e meta usados no cálculo e na publicação do painel.</p></div>
          <div class="rdo-admin-badges">
            <Badge variant="secondary">RNC</Badge>
            <Badge variant="outline">{{ monthsWithData }}/6 meses</Badge>
            <Badge :variant="isPublished ? 'success' : 'warning'">{{ isPublished ? "Publicado" : "Rascunho" }}</Badge>
          </div>
        </div>

        <div class="rdo-admin-context-grid">
          <PublicationPeriodField
            field-id="rnc-period"
            class="rdo-admin-period-field"
            :year="year"
            :semester="semester"
            :period-options="periodOptions"
            :available-periods="availablePeriods"
            :publish-period="cycle"
            :view-filter="viewFilter"
            :years-in-data="availableYears"
            @change="setPeriod"
            @update:view-filter="viewFilter = $event"
            @prepare-next-semester="setPeriod(nextWorkingPeriod(year, semester).year, nextWorkingPeriod(year, semester).semester)"
          />
          <div class="flex flex-col gap-1.5 rdo-admin-target-field">
            <Label for="rnc-target">Meta máxima (dias)</Label>
            <Input id="rnc-target" v-model.number="metaDias" type="number" step="0.1" min="0" />
            <p class="text-[11px] text-muted-foreground">Quanto menor, melhor. Meta padrão: 15 dias.</p>
          </div>
        </div>

        <p v-if="publication" class="rdo-admin-publication-note">
          Já existe uma publicação vigente para este período — v{{ publication.version }}, publicada em
          {{ formatDate(publication.publishedAt, true) }} por {{ publication.publishedBy?.name ?? "sistema" }}.
        </p>

        <div class="rdo-admin-actions">
          <Button variant="outline" size="sm" :disabled="loading" @click="load"><RotateCw :size="14" /> Atualizar</Button>
          <Button variant="outline" size="sm" @click="unitDialogOpen = true">
            <Ban :size="14" /> Ignorar unidades
            <Badge v-if="excludedUnits.length" variant="secondary">{{ excludedUnits.length }}</Badge>
          </Button>
          <Button variant="outline" size="sm" @click="justificationOpen = true"><Sparkles :size="14" /> Justificativa</Button>
          <Button variant="outline" size="sm" :disabled="!result" @click="exportPdf"><FileDown :size="14" /> Baixar PDF</Button>
          <Button v-if="canClear" variant="destructive" size="sm" :disabled="busy" @click="openClearModal">
            <Trash2 :size="14" /> Limpar registros
          </Button>
          <Button v-if="canPublish" variant="success" size="sm" :disabled="busy || loading || monthsWithData === 0" @click="publish">
            <Send :size="14" /> Publicar painel
          </Button>
        </div>
      </section>

      <template v-if="!loading && result">
        <p v-if="data?.lastImport" class="text-xs font-medium text-muted-foreground">
          Última importação: {{ data.lastImport.fileName }}
          <template v-if="data.lastImport.completedAt"> · {{ formatDate(data.lastImport.completedAt, true) }}</template>
        </p>
        <div class="rdo-admin-metrics">
          <article><span>RNC's Criadas</span><strong>{{ formatNumber(result.totalCriadas) }}</strong><small>Total no período consultado</small></article>
          <article class="is-good"><span>RNC's Tratadas</span><strong>{{ formatNumber(result.totalTratadas) }}</strong><small>{{ formatPercent(result.aderenciaTotal * 100) }} de aderência</small></article>
          <article><span>Dias de resolução</span><strong>{{ selectedMonthResult?.diasMedios === null || !selectedMonthResult ? "—" : formatNumber(selectedMonthResult.diasMedios, 1) }}</strong><small>{{ selectedMonthResult?.label ?? "Sem mês selecionado" }}</small></article>
          <article :class="selectedMonthResult && selectedMonthResult.chamados > 0 ? 'is-good' : 'is-warn'">
            <span>Aderência do mês</span>
            <strong>{{ selectedMonthResult && selectedMonthResult.chamados ? formatPercent((selectedMonthResult.solucionados / selectedMonthResult.chamados) * 100) : "—" }}</strong>
            <small>{{ selectedMonthResult ? `${selectedMonthResult.solucionados}/${selectedMonthResult.chamados} solucionadas` : "Sem dados" }}</small>
          </article>
        </div>

        <section class="rdo-admin-table-card">
          <header>
            <div><h3>Por mês</h3><p>RNC elaboradas, RNC tratadas e prazo médio de resolução pela data de criação.</p></div>
            <div class="rdo-admin-filter-pair">
              <div class="flex flex-col gap-1.5 rdo-admin-select-field"><Label for="rnc-month">Mês</Label><Select id="rnc-month" v-model="monthFilter"><option value="all">Todos</option><option v-for="month in availableMonths" :key="month" :value="String(month)">{{ MONTHS[month - 1] }}</option></Select></div>
              <div class="flex flex-col gap-1.5 rdo-admin-select-field"><Label for="rnc-year">Ano</Label><Select id="rnc-year" v-model="yearFilter"><option value="all">Todos</option><option v-for="item in availableYears" :key="item" :value="String(item)">{{ item }}</option></Select></div>
            </div>
          </header>
          <div class="table-wrap"><table class="data-table rdo-admin-table">
            <thead><tr><th>Mês</th><th class="numeric">RNC Elaboradas</th><th class="numeric">RNC Tratadas</th><th class="numeric">Dias de resolução</th><th>Situação</th></tr></thead>
            <tbody>
              <tr v-for="month in filteredMonths" :key="`${month.year}-${month.month}`" @click="selectedMonth = `${month.year}-${String(month.month + 1).padStart(2, '0')}`">
                <td>{{ month.label }}</td><td class="numeric">{{ formatNumber(month.chamados) }}</td><td class="numeric">{{ formatNumber(month.solucionados) }}</td><td class="numeric">{{ month.diasMedios === null ? "—" : formatNumber(month.diasMedios, 1) }}</td>
                <td><span class="badge" :class="month.dentroMeta === null ? '' : month.dentroMeta ? 'good' : 'bad'">{{ month.dentroMeta === null ? "Sem tratativa" : month.dentroMeta ? "Dentro da meta" : "Fora da meta" }}</span></td>
              </tr>
              <tr v-if="!filteredMonths.length"><td colspan="5" class="empty-cell">Nenhum mês encontrado para os filtros selecionados.</td></tr>
            </tbody>
          </table></div>
        </section>

        <section class="rdo-admin-table-card">
          <header>
            <div><h3>Por unidade</h3><p>RNC criadas, tratadas e aderência consolidada por unidade.</p></div>
            <div class="flex flex-col gap-1.5 rdo-admin-select-field"><Label for="rnc-unit">Unidade</Label><Select id="rnc-unit" v-model="unitFilter"><option value="all">Todas as unidades</option><option v-for="unit in units" :key="unit.name" :value="unit.name">{{ formatRncUnitLabel(unit.name) }}</option></Select></div>
          </header>
          <div class="table-wrap"><table class="data-table rdo-admin-table">
            <thead><tr><th>Unidade</th><th class="numeric">Criadas</th><th class="numeric">Tratadas</th><th class="numeric">Aderência</th></tr></thead>
            <tbody>
              <tr v-for="unit in filteredUnits" :key="unit.name"><td>{{ formatRncUnitLabel(unit.name) }} <Badge v-if="unit.excluded" variant="outline">ignorada</Badge></td><td class="numeric">{{ formatNumber(unit.criadas) }}</td><td class="numeric">{{ formatNumber(unit.tratadas) }}</td><td class="numeric">{{ formatPercent(unit.aderencia * 100) }}</td></tr>
              <tr v-if="!filteredUnits.length"><td colspan="4" class="empty-cell">Nenhuma unidade encontrada.</td></tr>
            </tbody>
          </table></div>
        </section>

        <section class="rdo-admin-table-card">
          <header><div><h3>Por Ofensor (causa raiz)</h3><p>Distribuição das não conformidades por origem identificada.</p></div></header>
          <div class="table-wrap"><table class="data-table rdo-admin-table">
            <thead><tr><th>Ofensor</th><th class="numeric">Quantidade</th><th class="numeric">%</th></tr></thead>
            <tbody><tr v-for="item in offenders" :key="item.name"><td>{{ item.name }}</td><td class="numeric">{{ formatNumber(item.count) }}</td><td class="numeric">{{ formatPercent(item.pct * 100) }}</td></tr><tr v-if="!offenders.length"><td colspan="3" class="empty-cell">Nenhum ofensor encontrado.</td></tr></tbody>
          </table></div>
        </section>
      </template>
      <div v-else-if="!loading" class="rdo-admin-empty"><span>Aguardando dados</span><strong>RNC</strong><p>Importe uma planilha para visualizar os resultados administrativos.</p></div>
      <div v-if="loading" class="loading-state"><div class="spinner" /></div>
    </div>
  </div>

  <AppModal :open="resultModal" title="Resultado da importação" @close="resultModal = false">
    <div v-if="uploadResult" class="stack">
      <p class="notice" :class="uploadResult.totals.rejected > 0 ? 'error' : 'success'">
        <CheckCircle2 v-if="!uploadResult.totals.rejected" :size="14" class="inline" /><AlertTriangle v-else :size="14" class="inline" />
        {{ uploadResult.totals.inserted }} inseridos, {{ uploadResult.totals.updated }} atualizados, {{ uploadResult.totals.ignored }} ignorados e {{ uploadResult.totals.rejected }} rejeitados ({{ uploadResult.durationMs }} ms).
      </p>
      <div v-for="file in uploadResult.files" :key="file.fileName" class="rdo-upload-file-result">
        <div class="rdo-upload-file-result-head"><FileSpreadsheet class="size-3.5" /><strong>{{ file.fileName }}</strong><span>{{ file.found }} linhas · {{ file.accepted }} aceitas · {{ file.rejected }} rejeitadas</span></div>
        <p v-for="(fileError, index) in file.errors" :key="index" class="notice error"><AlertTriangle :size="13" class="inline" /><template v-if="fileError.row">Linha {{ fileError.row }}: </template>{{ fileError.message }}</p>
      </div>
    </div>
    <template #actions><button class="btn primary" @click="resultModal = false">Fechar</button></template>
  </AppModal>

  <UnitExclusionDialog :open="unitDialogOpen" :units="unitOptions" :excluded="excludedUnits" :busy="busy" @update:open="unitDialogOpen = $event" @save="saveExcludedUnits" />
  <ClearRecordsDialog
    :open="clearModalOpen"
    title="Excluir registros do RNC"
    description="Os registros são apagados permanentemente do banco de dados. A publicação vigente não é afetada."
    :period-range="clearPeriodRange"
    :years-in-data="availableYears"
    :fetch-affected-count="fetchAffectedCount"
    affected-label="registros"
    :busy="busy"
    @update:open="clearModalOpen = $event"
    @update:period-range="clearPeriodRange = $event"
    @confirm="confirmClear"
  />
  <JustificationDialog :open="justificationOpen" module="rnc" :year="justificationYear" :month="justificationMonth" :target="metaDias" @close="justificationOpen = false" />
</template>
