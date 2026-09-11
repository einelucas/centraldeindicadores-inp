<script setup lang="ts">
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  ChevronDown,
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
import { notifyIndicatorDataChanged } from "~/utils/browser-events";
import { isWithinPeriodRange, MONTHS, periodToQuery } from "~/utils/period";
import { formatDate, formatNumber, formatPercent } from "~/utils/format";
import { exportRdoPdf } from "~/logic/features/rdo/exports/pdf";
import { formatRdoUnitLabel } from "~/logic/features/rdo/utils/units";
import type { RdoResult } from "~/logic/features/rdo/types";

defineProps<{ canPublish: boolean; canClear: boolean }>();

const api = useApi();
const upload = useFileUpload();
const exporter = useExport();
const auth = useAuthStore();

const { year, semester, cycle, setPeriod } = useReadingContextCycle();
const { availablePeriods, periodOptions, loadAvailablePeriods } =
  usePublicationPeriodOptions("rdo", year, semester);

/** `undefined` = tabela segue o período de trabalho; `null`/`PeriodRange` =
 * filtro de consulta independente, definido via "Detalhar meses". */
const viewFilter = ref<PeriodRange | null | undefined>(undefined);
const queryPeriod = computed<PeriodRange | null | undefined>(() =>
  viewFilter.value !== undefined ? viewFilter.value : cycle.value,
);

const target = ref(80);
const data = ref<Record<string, unknown> | null>(null);
const loading = ref(true);
const busy = ref(false);
const message = ref("");
const messageTone = ref<"success" | "error" | "">("");
const publication = ref<PublicationEnvelope["publication"]>(null);

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
const justificationYear = computed(() => cycle.value.endYear);
const justificationMonth = computed(() => cycle.value.endMonth);

const unitFilter = ref("all");
const monthFilter = ref("all");
const yearFilter = ref("all");
const detailPeriodFilter = ref<PeriodRange | null>(null);

const result = computed<Record<string, unknown>>(() => (data.value?.result as Record<string, unknown>) ?? {});
function list(key: string): Array<Record<string, unknown>> {
  return Array.isArray(result.value[key]) ? (result.value[key] as Array<Record<string, unknown>>) : [];
}
const details = computed(() =>
  Array.isArray(data.value?.detalhe) ? (data.value?.detalhe as Array<Record<string, unknown>>) : [],
);
const filteredDetails = computed(() => {
  if (!detailPeriodFilter.value) return details.value;
  return details.value.filter((row) => {
    const parsed = new Date(String(row.data));
    if (Number.isNaN(parsed.getTime())) return false;
    return isWithinPeriodRange(parsed.getFullYear(), parsed.getMonth() + 1, detailPeriodFilter.value);
  });
});
const filteredUnits = computed(() =>
  unitFilter.value === "all" ? list("units") : list("units").filter((row) => String(row.name) === unitFilter.value),
);
const filteredUnitAverage = computed(() =>
  filteredUnits.value.length
    ? filteredUnits.value.reduce((sum, row) => sum + Number(row.aderencia ?? 0), 0) / filteredUnits.value.length
    : 0,
);
const availableYears = computed(() =>
  Array.from(new Set(list("months").map((row) => Number(row.year)))).filter(Number.isFinite).sort((a, b) => b - a),
);
const availableMonths = computed(() =>
  Array.from(new Set(list("months").map((row) => Number(row.month)))).filter(Number.isFinite).sort((a, b) => a - b),
);
const filteredMonths = computed(() =>
  list("months").filter(
    (row) =>
      (yearFilter.value === "all" || Number(row.year) === Number(yearFilter.value)) &&
      (monthFilter.value === "all" || Number(row.month) === Number(monthFilter.value)),
  ),
);
const monthsWithData = computed(() => list("months").length);
const isPublished = computed(() => {
  const pub = publication.value;
  if (!pub) return false;
  return pub.cycleYear === year.value && pub.cycleSemester === semester.value;
});
// `code` é o código normalizado no servidor (o que `excludedUnits` de fato
// guarda) — usar `unit.name` (rótulo de exibição) aqui fazia o diálogo de
// exclusão nunca reconhecer uma unidade já marcada, e "desmarcar" virava um
// novo `add` sob outra grafia em vez de remover a existente.
const unitOptions = computed(() =>
  list("units").map((unit) => ({ code: String(unit.code), label: formatRdoUnitLabel(String(unit.name)) })),
);

function showMessage(text: string, tone: "success" | "error" = "success") {
  message.value = text;
  messageTone.value = tone;
}

async function load() {
  loading.value = true;
  message.value = "";
  try {
    const query: Record<string, unknown> = { ...periodToQuery(queryPeriod.value), threshold: target.value };
    data.value = await api.get<Record<string, unknown>>("/rdo", query);
    target.value = Number(data.value.threshold ?? 0.8) * 100;
    excludedUnits.value = ((result.value.excludedUnits as string[] | undefined) ?? (data.value.excludedUnits as string[] | undefined) ?? []);
  } catch (cause) {
    showMessage(cause instanceof Error ? cause.message : "Erro ao carregar dados.", "error");
  } finally {
    loading.value = false;
  }
}

async function loadPublication() {
  try {
    const body = await api.get<PublicationEnvelope>("/publicacoes/rdo", periodToQuery(cycle.value));
    publication.value = body.publication;
  } catch {
    publication.value = null;
  }
}

function onDragOver(event: DragEvent) {
  event.preventDefault();
  dragging.value = true;
}
function onDragLeave() {
  dragging.value = false;
}
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
  const unitsBefore = new Set(list("units").map((unit) => String(unit.name)));
  try {
    const outcome = await upload.uploadFiles("rdo", files);
    uploadResult.value = outcome;
    resultModal.value = true;
    showMessage(
      `Importação concluída: ${outcome.totals.inserted} inseridos, ${outcome.totals.updated} atualizados, ` +
        `${outcome.totals.ignored} ignorados e ${outcome.totals.rejected} rejeitados.`,
    );
    await load();
    await loadAvailablePeriods();
    await loadPublication();
    const newUnits = list("units").map((unit) => String(unit.name)).filter((code) => !unitsBefore.has(code));
    if (newUnits.length) unitDialogOpen.value = true;
  } catch (cause) {
    showMessage(cause instanceof Error ? cause.message : "Erro durante a importação.", "error");
  } finally {
    uploading.value = false;
    uploadingFileCount.value = 0;
    if (fileInput.value) fileInput.value.value = "";
  }
}

async function saveExcludedUnits(next: string[]) {
  busy.value = true;
  try {
    await api.patch("/rdo", { excludedUnits: next });
    excludedUnits.value = next;
    unitDialogOpen.value = false;
    showMessage("Unidades atualizadas e indicador recalculado.");
    await load();
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
  const body = await api.get<{ count: number }>("/rdo/registros", period ? periodToQuery(period) : {});
  return body.count;
}
async function confirmClear() {
  busy.value = true;
  try {
    await api.delete("/rdo/registros", clearPeriodRange.value ? periodToQuery(clearPeriodRange.value) : { all: true });
    clearModalOpen.value = false;
    showMessage("Registros excluídos. A publicação vigente foi preservada.");
    await load();
  } catch (cause) {
    showMessage(cause instanceof Error ? cause.message : "Erro ao excluir registros.", "error");
  } finally {
    busy.value = false;
  }
}

async function publish() {
  busy.value = true;
  try {
    await api.post("/publicacoes/rdo", { ...periodToQuery(cycle.value), threshold: target.value });
    showMessage("Painel publicado com sucesso.");
    notifyIndicatorDataChanged();
    window.dispatchEvent(new Event("rdo:published"));
    await loadPublication();
  } catch (cause) {
    showMessage(cause instanceof Error ? cause.message : "Erro ao publicar.", "error");
  } finally {
    busy.value = false;
  }
}

async function editStatus(row: Record<string, unknown>, status: string) {
  try {
    await api.patch("/rdo/registros", { id: row.id, status });
    row.status = status;
    showMessage("Status atualizado.");
  } catch (cause) {
    showMessage(cause instanceof Error ? cause.message : "Erro ao editar status.", "error");
  }
}

function buildRdoResult(): RdoResult {
  const r = result.value;
  return {
    threshold: target.value / 100,
    excludedUnits: excludedUnits.value,
    period: (queryPeriod.value ?? null) as PeriodRange | null,
    totalEmitidos: Number(r.totalEmitidos ?? 0),
    totalAprovados: Number(r.totalAprovados ?? 0),
    totalRevisar: Number(r.totalRevisar ?? 0),
    totalPreenchendo: Number(r.totalPreenchendo ?? 0),
    units: list("units").map((unit) => ({
      name: String(unit.name),
      code: String(unit.code),
      emitidos: Number(unit.emitidos),
      aprovados: Number(unit.aprovados),
      aderencia: Number(unit.aderencia),
      excluded: Boolean(unit.excluded),
    })),
    unitAvg: Number(r.unitAvg ?? 0),
    months: list("months").map((month) => ({
      label: String(month.label),
      year: Number(month.year),
      month: Number(month.month),
      emitidos: Number(month.emitidos),
      aprovados: Number(month.aprovados),
      aderencia: Number(month.aderencia),
    })),
  };
}
function exportPdf() {
  exportRdoPdf(buildRdoResult(), target.value);
}
function exportExcel() {
  exporter.excel("rdo-administracao", details.value);
}

watch(queryPeriod, load, { deep: true });
watch(cycle, loadPublication, { deep: true });
onMounted(() => {
  void load();
  void loadPublication();
});
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
          <strong>{{ uploading ? "Enviando e processando arquivos…" : "Importar relatórios diários de obra" }}</strong>
          <small v-if="uploading">
            {{ uploadingFileCount === 1 ? "1 arquivo" : `${uploadingFileCount} arquivos` }} — isso pode levar alguns
            segundos, não feche esta página.
          </small>
          <small v-else>Arraste os arquivos aqui ou clique para selecionar planilhas Excel/CSV do sistema de RDO.</small>
          <input
            ref="fileInput"
            type="file"
            hidden
            multiple
            accept=".xlsx,.xls,.xlsm,.xlsb,.xltx,.xlt,.csv"
            :disabled="uploading"
            @change="onFileInputChange"
          />
        </label>
      </div>

      <div v-if="message" class="notice" :class="messageTone">{{ message }}</div>

      <section class="rdo-admin-context">
        <div class="rdo-admin-context-head">
          <div>
            <h3>Contexto de publicação</h3>
            <p>Período e meta usados no cálculo e na publicação do painel.</p>
          </div>
          <div class="rdo-admin-badges">
            <Badge variant="secondary">RDO</Badge>
            <Badge variant="outline">{{ monthsWithData }}/6 meses</Badge>
            <Badge :variant="isPublished ? 'success' : 'warning'">{{ isPublished ? "Publicado" : "Rascunho" }}</Badge>
          </div>
        </div>

        <div class="rdo-admin-context-grid">
          <PublicationPeriodField
            field-id="rdo-period"
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
            <Label for="rdo-target">Meta de aderência (%)</Label>
            <Input id="rdo-target" v-model.number="target" type="number" step="0.01" min="0" />
            <p class="text-[11px] text-muted-foreground">Meta padrão: 80%.</p>
          </div>
        </div>

        <p v-if="publication" class="rdo-admin-publication-note">
          Já existe uma publicação vigente para este período — v{{ publication.version }}, publicada em
          {{ formatDate(publication.publishedAt, true) }} por {{ publication.publishedBy?.name ?? "sistema" }}.
          Publicar novamente cria uma nova versão.
        </p>

        <div class="rdo-admin-actions">
          <Button variant="outline" size="sm" :disabled="loading" @click="load"><RotateCw :size="14" /> Atualizar</Button>
          <Button variant="outline" size="sm" @click="unitDialogOpen = true">
            <Ban :size="14" /> Ignorar unidades
            <Badge v-if="excludedUnits.length" variant="secondary">{{ excludedUnits.length }}</Badge>
          </Button>
          <Button variant="outline" size="sm" @click="justificationOpen = true"><Sparkles :size="14" /> Justificativa</Button>
          <Button variant="outline" size="sm" @click="exportExcel">Exportar Excel</Button>
          <Button variant="outline" size="sm" @click="exportPdf"><FileDown :size="14" /> Exportar PDF</Button>
          <Button v-if="canClear" variant="destructive" size="sm" :disabled="busy" @click="openClearModal">
            <Trash2 :size="14" /> Limpar registros
          </Button>
          <Button v-if="canPublish" variant="success" size="sm" :disabled="busy || loading || !data" @click="publish">
            <Send :size="14" /> Publicar painel
          </Button>
        </div>
      </section>

      <template v-if="!loading && data">
        <div class="rdo-admin-metrics">
          <article>
            <span>Total emitidos</span>
            <strong>{{ formatNumber(result.totalEmitidos) }}</strong>
            <small>Relatórios encontrados</small>
          </article>
          <article class="is-good">
            <span>Aprovados</span>
            <strong>{{ formatPercent(result.totalEmitidos ? (Number(result.totalAprovados) / Number(result.totalEmitidos)) * 100 : 0) }}</strong>
            <small>{{ formatNumber(result.totalAprovados) }} relatórios</small>
          </article>
          <article class="is-warn">
            <span>A revisar</span>
            <strong>{{ formatPercent(result.totalEmitidos ? (Number(result.totalRevisar) / Number(result.totalEmitidos)) * 100 : 0) }}</strong>
            <small>{{ formatNumber(result.totalRevisar) }} relatórios</small>
          </article>
          <article>
            <span>Preenchendo</span>
            <strong>{{ formatPercent(result.totalEmitidos ? (Number(result.totalPreenchendo) / Number(result.totalEmitidos)) * 100 : 0) }}</strong>
            <small>{{ formatNumber(result.totalPreenchendo) }} relatórios</small>
          </article>
        </div>

        <section class="rdo-admin-table-card">
          <header>
            <div><h3>Aderência por unidade</h3><p>Nº RDO emitidos x aprovados, por obra/unidade.</p></div>
            <div class="flex flex-col gap-1.5 rdo-admin-select-field">
              <Label for="rdo-unit-filter">Unidade</Label>
              <Select id="rdo-unit-filter" v-model="unitFilter">
                <option value="all">Todas as unidades</option>
                <option v-for="unit in list('units')" :key="String(unit.name)" :value="String(unit.name)">{{ unit.name }}</option>
              </Select>
            </div>
          </header>
          <div class="table-wrap">
            <table class="data-table rdo-admin-table">
              <thead>
                <tr><th>Unidade</th><th class="numeric">Emitidos</th><th class="numeric">Aprovados</th><th class="numeric">Aderência</th><th>Situação</th></tr>
              </thead>
              <tbody>
                <tr v-for="unit in filteredUnits" :key="String(unit.name)">
                  <td>{{ unit.name }}</td>
                  <td class="numeric">{{ formatNumber(unit.emitidos) }}</td>
                  <td class="numeric">{{ formatNumber(unit.aprovados) }}</td>
                  <td class="numeric">{{ formatPercent(Number(unit.aderencia) * 100) }}</td>
                  <td>
                    <span class="badge" :class="unit.excluded ? '' : Number(unit.aderencia) * 100 >= target ? 'good' : 'bad'">
                      {{ unit.excluded ? "Ignorada" : Number(unit.aderencia) * 100 >= target ? "Dentro da meta" : "Abaixo da meta" }}
                    </span>
                  </td>
                </tr>
                <tr v-if="filteredUnits.length" class="rdo-admin-average">
                  <td>{{ unitFilter === "all" ? "Média das unidades" : "Unidade selecionada" }}</td>
                  <td /><td />
                  <td class="numeric">{{ formatPercent(filteredUnitAverage * 100) }}</td>
                  <td />
                </tr>
                <tr v-if="!filteredUnits.length"><td colspan="5" class="empty-cell">Nenhuma unidade encontrada para o filtro selecionado.</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="rdo-admin-table-card">
          <header>
            <div><h3>Aderência por mês</h3><p>Consolidado mensal de todas as unidades.</p></div>
            <div class="rdo-admin-filter-pair">
              <div class="flex flex-col gap-1.5 rdo-admin-select-field">
                <Label for="rdo-month-filter">Mês</Label>
                <Select id="rdo-month-filter" v-model="monthFilter">
                  <option value="all">Todos os meses</option>
                  <option v-for="month in availableMonths" :key="month" :value="String(month)">{{ MONTHS[month - 1] ?? `Mês ${month}` }}</option>
                </Select>
              </div>
              <div class="flex flex-col gap-1.5 rdo-admin-select-field">
                <Label for="rdo-year-filter">Ano</Label>
                <Select id="rdo-year-filter" v-model="yearFilter">
                  <option value="all">Todos</option>
                  <option v-for="yr in availableYears" :key="yr" :value="String(yr)">{{ yr }}</option>
                </Select>
              </div>
            </div>
          </header>
          <div class="table-wrap">
            <table class="data-table rdo-admin-table">
              <thead>
                <tr><th>Mês</th><th class="numeric">Emitidos</th><th class="numeric">Aprovados</th><th class="numeric">Aderência</th><th>Situação</th></tr>
              </thead>
              <tbody>
                <tr v-for="month in filteredMonths" :key="`${month.year}-${month.month}`">
                  <td>{{ month.label }}</td>
                  <td class="numeric">{{ formatNumber(month.emitidos) }}</td>
                  <td class="numeric">{{ formatNumber(month.aprovados) }}</td>
                  <td class="numeric">{{ formatPercent(Number(month.aderencia) * 100) }}</td>
                  <td>
                    <span class="badge" :class="Number(month.aderencia) * 100 >= target ? 'good' : 'bad'">
                      {{ Number(month.aderencia) * 100 >= target ? "Dentro da meta" : "Abaixo da meta" }}
                    </span>
                  </td>
                </tr>
                <tr v-if="!filteredMonths.length"><td colspan="5" class="empty-cell">Nenhum mês encontrado para os filtros selecionados.</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <details v-if="details.length" class="rdo-admin-table-card rdo-collapsible">
          <summary>
            <div><h3>Detalhamento</h3><p>Registros individuais — administradores podem corrigir o status manualmente.</p></div>
            <ChevronDown class="rdo-collapsible-chevron" :size="18" />
          </summary>
          <div class="rdo-collapsible-body">
            <div class="rdo-admin-filter-pair">
              <PeriodRangeFilter v-model="detailPeriodFilter" label="Período" :years-in-data="availableYears" />
            </div>
            <div class="table-wrap">
              <table class="data-table rdo-admin-table">
                <thead>
                  <tr><th>Data</th><th>Unidade</th><th>Grupo</th><th>Disciplina</th><th>Status</th><th>ID</th></tr>
                </thead>
                <tbody>
                  <tr v-for="row in filteredDetails.slice(0, 200)" :key="String(row.id)">
                    <td>{{ formatDate(row.data) }}</td>
                    <td>{{ row.unidade }}</td>
                    <td>{{ row.grupo || "—" }}</td>
                    <td>{{ row.disciplina || "—" }}</td>
                    <td>
                      <select v-if="auth.isAdmin" class="input" :value="row.status" @change="editStatus(row, ($event.target as HTMLSelectElement).value)">
                        <option>Aprovado</option>
                        <option>Revisar Relatório</option>
                        <option>Preenchendo Relatório</option>
                      </select>
                      <span v-else>{{ row.status }}</span>
                    </td>
                    <td>{{ row.relatorio_id || "—" }}</td>
                  </tr>
                  <tr v-if="!filteredDetails.length"><td colspan="6" class="empty-cell">Nenhum registro encontrado para o período selecionado.</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </details>
      </template>
      <div v-else-if="!loading" class="rdo-admin-empty">
        <span>Aguardando dados</span>
        <strong>RDO</strong>
        <p>Importe uma planilha para visualizar os resultados administrativos.</p>
      </div>
      <div v-if="loading" class="loading-state"><div class="spinner" /></div>
    </div>
  </div>

  <AppModal :open="resultModal" title="Resultado da importação" @close="resultModal = false">
    <div v-if="uploadResult" class="stack">
      <p class="notice" :class="uploadResult.totals.rejected > 0 ? 'error' : 'success'">
        <CheckCircle2 v-if="!uploadResult.totals.rejected" :size="14" class="inline" />
        <AlertTriangle v-else :size="14" class="inline" />
        {{ uploadResult.totals.inserted }} inseridos, {{ uploadResult.totals.updated }} atualizados,
        {{ uploadResult.totals.ignored }} ignorados e {{ uploadResult.totals.rejected }} rejeitados
        ({{ uploadResult.durationMs }} ms).
      </p>
      <div v-for="file in uploadResult.files" :key="file.fileName" class="rdo-upload-file-result">
        <div class="rdo-upload-file-result-head">
          <FileSpreadsheet class="size-3.5" />
          <strong>{{ file.fileName }}</strong>
          <span>{{ file.found }} linhas · {{ file.accepted }} aceitas · {{ file.rejected }} rejeitadas</span>
        </div>
        <p v-for="(error, index) in file.errors" :key="index" class="notice error">
          <AlertTriangle :size="13" class="inline" />
          <template v-if="error.row">Linha {{ error.row }}: </template>{{ error.message }}
        </p>
      </div>
    </div>
    <template #actions>
      <button class="btn primary" @click="resultModal = false">Fechar</button>
    </template>
  </AppModal>

  <UnitExclusionDialog
    :open="unitDialogOpen"
    :units="unitOptions"
    :excluded="excludedUnits"
    :busy="busy"
    @update:open="unitDialogOpen = $event"
    @save="saveExcludedUnits"
  />

  <ClearRecordsDialog
    :open="clearModalOpen"
    title="Excluir registros do RDO"
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

  <JustificationDialog
    :open="justificationOpen"
    module="rdo"
    :year="justificationYear"
    :month="justificationMonth"
    :target="target"
    @close="justificationOpen = false"
  />
</template>
