<script setup lang="ts">
import {
  AlertTriangle,
  Ban,
  ChevronDown,
  ChevronRight,
  FileDown,
  Info,
  Loader2,
  RotateCw,
  Save,
  Send,
  Sparkles,
  Trash2,
  UploadCloud,
  X,
} from "lucide-vue-next";
import type { PeriodRange, PublicationEnvelope } from "~/types/api";
import { notifyIndicatorDataChanged } from "~/utils/browser-events";
import { periodToQuery } from "~/utils/period";
import { MONTH_NAMES_FULL } from "~/utils/dates";
import { formatDate, formatPercent } from "~/utils/format";
import { exportIdpPdf } from "~/logic/features/idp/exports/pdf";
import { formatUnitLabel, normalizeUnitCode } from "~/logic/lib/units";
import { parseIdpFile } from "~/logic/features/idp/importers";
import type { IdpNormalizedRecord, IdpResult } from "~/logic/features/idp/types";

defineProps<{ canPublish: boolean; canClear: boolean }>();

const api = useApi();
const imports = useImports();
const exporter = useExport();

const { year, semester, cycle, setPeriod } = useReadingContextCycle();
const { availablePeriods, periodOptions, loadAvailablePeriods, detectNewPeriod } =
  usePublicationPeriodOptions("idp", year, semester);

/** `undefined` = tabela segue o período de trabalho; `null`/`PeriodRange` =
 * filtro de consulta independente, definido via "Detalhar meses". */
const viewFilter = ref<PeriodRange | null | undefined>(undefined);
const queryPeriod = computed<PeriodRange | null | undefined>(() =>
  viewFilter.value !== undefined ? viewFilter.value : cycle.value,
);

const threshold = ref(90);
const data = ref<Record<string, unknown> | null>(null);
const loading = ref(true);
const busy = ref(false);
const message = ref("");
const messageTone = ref<"success" | "error" | "">("");
const publication = ref<PublicationEnvelope["publication"]>(null);

const dragging = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);

interface PendingFile {
  id: string;
  fileName: string;
  record: IdpNormalizedRecord | null;
  error: string | null;
}
const pendingFiles = ref<PendingFile[]>([]);
const progress = ref<{
  currentBatch: number;
  totalBatches: number;
  inserted: number;
  ignored: number;
  updated: number;
  rejected: number;
} | null>(null);

const excludedUnits = ref<string[]>([]);
const unitDialogOpen = ref(false);

const excludedDisciplinesDraft = ref("");

const clearModalOpen = ref(false);
const clearPeriodRange = ref<PeriodRange | null>(null);

const justificationOpen = ref(false);

const selectedUnit = ref("");
const expanded = ref<Set<string>>(new Set());

const result = computed(() => (data.value?.result as Record<string, unknown>) ?? {});
function resultList(key: string): Array<Record<string, unknown>> {
  return Array.isArray(result.value[key]) ? (result.value[key] as Array<Record<string, unknown>>) : [];
}
const unitRows = computed(() => resultList("unitRows"));
const disciplineRows = computed(() => resultList("disciplineRows"));
const monthlyRows = computed(() => resultList("monthly"));
const documents = computed(() =>
  Array.isArray(data.value?.documents) ? (data.value?.documents as Array<Record<string, unknown>>) : [],
);
const years = computed(() => (Array.isArray(data.value?.years) ? (data.value?.years as number[]) : []));
const activeDocuments = computed(() => Number(result.value.activeDocuments ?? 0));
const selectedYear = computed(() => Number(data.value?.selectedYear ?? year.value));
const selectedMonth = computed(() => Number(data.value?.selectedMonth ?? 1));

function competenceLabel(y: number, m: number): string {
  return `${MONTH_NAMES_FULL[m - 1] ?? m}/${y}`;
}
function discRow(name: string): Record<string, unknown> | undefined {
  return disciplineRows.value.find((row) => row.disciplina === name);
}
const civilAderencia = computed(() => discRow("01 - Civil")?.aderencia as number | null | undefined);
const mecanicaAderencia = computed(() => discRow("02 - Mecânica")?.aderencia as number | null | undefined);
const eletricaAderencia = computed(() => discRow("04 - Elétrica")?.aderencia as number | null | undefined);

const unitOptions = computed(() => {
  const codes = new Set<string>();
  for (const doc of documents.value) codes.add(normalizeUnitCode(String(doc.unit ?? "")));
  for (const code of excludedUnits.value) codes.add(normalizeUnitCode(code));
  codes.delete("");
  return Array.from(codes)
    .sort((a, b) => formatUnitLabel(a).localeCompare(formatUnitLabel(b), "pt-BR"))
    .map((code) => ({ code, label: formatUnitLabel(code) }));
});

const isPublished = computed(() => {
  const pub = publication.value;
  if (!pub) return false;
  return pub.cycleYear === year.value && pub.cycleSemester === semester.value;
});

function shortDate(value: unknown): string {
  if (!value) return "—";
  const text = String(value);
  const [datePart] = text.split("T");
  const parts = (datePart ?? text).split("-");
  if (parts.length !== 3) return formatDate(value);
  const [y, m, d] = parts;
  return `${d}/${m}/${y}`;
}
function periodLabel(start: unknown, end: unknown): string {
  if (!start && !end) return "Não identificado";
  return `${shortDate(start)} → ${shortDate(end)}`;
}

function accumulated(value: unknown): string {
  const number = Number(value ?? 0);
  return `${number.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
}

const selectedUnitDetail = computed(() => unitRows.value.find((row) => row.unit === selectedUnit.value) ?? null);

function showMessage(text: string, tone: "success" | "error" = "success") {
  message.value = text;
  messageTone.value = tone;
}

function toggle(key: string) {
  const next = new Set(expanded.value);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  expanded.value = next;
}

async function load() {
  loading.value = true;
  message.value = "";
  try {
    const query: Record<string, unknown> = { ...periodToQuery(queryPeriod.value), threshold: threshold.value };
    data.value = await api.get<Record<string, unknown>>("/idp", query);
    threshold.value = Number(data.value.threshold ?? 0.9) * 100;
    excludedDisciplinesDraft.value = (
      (data.value.excludedDisciplines as string[] | undefined) ?? []
    ).join("\n");
    excludedUnits.value = (result.value.excludedUnits as string[] | undefined) ?? [];
    if (!unitRows.value.some((row) => row.unit === selectedUnit.value)) {
      selectedUnit.value = (unitRows.value[0]?.unit as string | undefined) ?? "";
    }
  } catch (cause) {
    showMessage(cause instanceof Error ? cause.message : "Erro ao carregar dados.", "error");
  } finally {
    loading.value = false;
  }
}

async function loadPublication() {
  try {
    const body = await api.get<PublicationEnvelope>("/publicacoes/idp", periodToQuery(cycle.value));
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
  if (files.length) await prepareFiles(files);
}
function onFileInputChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files ?? []);
  if (files.length) void prepareFiles(files);
}

async function prepareFiles(files: File[]) {
  busy.value = true;
  message.value = "";
  try {
    const parsed: PendingFile[] = [];
    for (let index = 0; index < files.length; index += 1) {
      const file = files[index]!;
      const result = await parseIdpFile(file);
      parsed.push({ ...result, id: `${Date.now()}-${index}-${file.name}` });
    }
    pendingFiles.value = [...pendingFiles.value, ...parsed];
    if (parsed.some((item) => item.record)) {
      showMessage(
        "RSOs lidos. Confira unidade, número da versão, mês de referência e período antes de importar.",
      );
      const known = new Set(unitOptions.value.map((option) => option.code));
      const hasNewUnit = parsed.some(
        (item) => item.record && !known.has(normalizeUnitCode(item.record.unit)),
      );
      if (hasNewUnit) unitDialogOpen.value = true;
    }
  } catch (cause) {
    showMessage(cause instanceof Error ? cause.message : "Falha ao ler os PDFs RSO.", "error");
  } finally {
    busy.value = false;
    if (fileInput.value) fileInput.value.value = "";
  }
}

function updatePending(id: string, updater: (record: IdpNormalizedRecord) => IdpNormalizedRecord) {
  pendingFiles.value = pendingFiles.value.map((item) =>
    item.id === id && item.record ? { ...item, record: updater(item.record) } : item,
  );
}

function removePending(id: string) {
  pendingFiles.value = pendingFiles.value.filter((item) => item.id !== id);
}

function inputMonthValue(record: IdpNormalizedRecord): string {
  if (!record.referenceYear || !record.referenceMonth) return "";
  return `${record.referenceYear}-${String(record.referenceMonth).padStart(2, "0")}`;
}

function isPendingRecordValid(record: IdpNormalizedRecord | null): record is IdpNormalizedRecord {
  return Boolean(
    record &&
      record.unit.trim() &&
      Number.isInteger(record.rsoNumero) &&
      (record.rsoNumero ?? 0) > 0 &&
      Number.isInteger(record.referenceYear) &&
      Number.isInteger(record.referenceMonth) &&
      (record.referenceMonth ?? 0) >= 1 &&
      (record.referenceMonth ?? 0) <= 12 &&
      record.referenceSource !== "UNRESOLVED" &&
      record.execucaoFases.length > 0,
  );
}

const validPendingCount = computed(
  () => pendingFiles.value.filter((item) => isPendingRecordValid(item.record)).length,
);
const invalidPendingCount = computed(
  () => pendingFiles.value.filter((item) => item.record && !isPendingRecordValid(item.record)).length,
);

async function importPendingFiles() {
  const records = pendingFiles.value.map((item) => item.record).filter(isPendingRecordValid);
  if (!records.length) {
    showMessage("Nenhum RSO está completo para importação. Revise os campos destacados.", "error");
    return;
  }
  busy.value = true;
  message.value = "";
  progress.value = { currentBatch: 0, totalBatches: 0, inserted: 0, ignored: 0, updated: 0, rejected: 0 };
  try {
    const fileName = records.map((record) => record.fileName).join(", ");
    const outcome = await imports.send(
      "idp",
      fileName,
      records as unknown as Array<Record<string, unknown>>,
      (current) => {
        progress.value = {
          currentBatch: current.batch,
          totalBatches: current.totalBatches,
          inserted: current.totals.inserted,
          ignored: current.totals.ignored,
          updated: current.totals.updated,
          rejected: current.totals.rejected,
        };
      },
    );
    let importMessage = `Importação concluída: ${outcome.totals.inserted} nova(s) versão(ões), ${outcome.totals.updated} corrigida(s), ${outcome.totals.ignored} idêntica(s) e ${outcome.totals.rejected} rejeitada(s).`;
    const newPeriodMessage = detectNewPeriod(
      records.map((record) => ({ year: record.referenceYear!, month: record.referenceMonth! })),
      setPeriod,
    );
    if (newPeriodMessage) importMessage += ` ${newPeriodMessage}`;
    showMessage(importMessage);
    pendingFiles.value = [];
    notifyIndicatorDataChanged();
    await load();
    await loadAvailablePeriods();
    await loadPublication();
  } catch (cause) {
    showMessage(cause instanceof Error ? cause.message : "Falha na importação.", "error");
  } finally {
    busy.value = false;
    progress.value = null;
  }
}

async function saveExcludedUnits(next: string[]) {
  busy.value = true;
  try {
    await api.patch("/configuracoes", { key: "idp.excludedUnits", value: next });
    excludedUnits.value = next;
    unitDialogOpen.value = false;
    showMessage("Unidades ignoradas atualizadas e indicador recalculado.");
    await load();
  } catch (cause) {
    showMessage(cause instanceof Error ? cause.message : "Falha ao salvar as unidades ignoradas.", "error");
  } finally {
    busy.value = false;
  }
}

async function saveExcludedDisciplines() {
  const disciplines = excludedDisciplinesDraft.value
    .split(/[\r\n,;]+/)
    .map((item) => item.trim())
    .filter(Boolean);
  busy.value = true;
  try {
    await api.patch("/configuracoes", { key: "idp.excludedDisciplines", value: disciplines });
    showMessage("Disciplinas excluídas atualizadas.");
    await load();
  } catch (cause) {
    showMessage(cause instanceof Error ? cause.message : "Falha ao salvar as exclusões.", "error");
  } finally {
    busy.value = false;
  }
}

async function publish() {
  busy.value = true;
  try {
    await api.post("/publicacoes/idp", { ...periodToQuery(cycle.value), threshold: threshold.value });
    showMessage("IDP publicado com os RSOs exatos da competência mais recente do semestre.");
    notifyIndicatorDataChanged();
    await loadPublication();
  } catch (cause) {
    showMessage(cause instanceof Error ? cause.message : "Falha ao publicar o IDP.", "error");
  } finally {
    busy.value = false;
  }
}

function openClearModal() {
  clearPeriodRange.value = null;
  clearModalOpen.value = true;
}
async function fetchAffectedCount(period: PeriodRange | null): Promise<number> {
  const body = await api.get<{ count: number }>("/idp/registros", period ? periodToQuery(period) : {});
  return body.count;
}
async function confirmClear() {
  busy.value = true;
  try {
    await api.delete("/idp/registros", clearPeriodRange.value ? periodToQuery(clearPeriodRange.value) : { all: true });
    clearModalOpen.value = false;
    showMessage("Registros excluídos. A publicação vigente foi preservada.");
    notifyIndicatorDataChanged();
    pendingFiles.value = [];
    await load();
  } catch (cause) {
    showMessage(cause instanceof Error ? cause.message : "Falha ao limpar os registros.", "error");
  } finally {
    busy.value = false;
  }
}

function exportPdf() {
  const r = result.value;
  const idpResult: IdpResult = {
    threshold: threshold.value / 100,
    excludedDisciplines: (r.excludedDisciplines as string[] | undefined) ?? [],
    excludedUnits: (r.excludedUnits as string[] | undefined) ?? [],
    selectedYear: Number(r.selectedYear ?? selectedYear.value),
    selectedMonth: Number(r.selectedMonth ?? selectedMonth.value),
    historyStartYear: Number(r.historyStartYear ?? 0),
    historyMonthStart: Number(r.historyMonthStart ?? 1),
    historyEndYear: Number(r.historyEndYear ?? 0),
    historyMonthEnd: Number(r.historyMonthEnd ?? 1),
    activeDocuments: activeDocuments.value,
    aderenciaGeral: (r.aderenciaGeral as number | null) ?? null,
    totalPrevistoMedio: Number(r.totalPrevistoMedio ?? 0),
    totalRealMedio: Number(r.totalRealMedio ?? 0),
    unitRows: unitRows.value as unknown as IdpResult["unitRows"],
    disciplineRows: disciplineRows.value as unknown as IdpResult["disciplineRows"],
    monthly: monthlyRows.value as unknown as IdpResult["monthly"],
  };
  exportIdpPdf(idpResult);
}
function exportExcel() {
  exporter.excel(
    "idp-administracao",
    documents.value.map((doc) => ({
      unidade: doc.unit,
      rso: doc.rsoNumero,
      competencia: `${doc.referenceMonth}/${doc.referenceYear}`,
      arquivo: doc.fileName,
      ativo: doc.active ? "sim" : "não",
    })),
  );
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
        :class="{ 'rdo-upload-zone--dragging': dragging, 'rdo-upload-zone--busy': busy }"
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
            <Loader2 v-if="busy" :size="21" class="animate-spin" />
            <UploadCloud v-else :size="21" />
          </span>
          <strong>{{ busy ? "Lendo PDFs…" : "Importar RSOs do IDP" }}</strong>
          <small>
            Arraste os PDFs do RSO aqui ou clique para selecionar. O sistema lê Unidade, RSO Nº, Mês ref.,
            Período, Emissão, Execução e disciplinas.
          </small>
          <input
            ref="fileInput"
            type="file"
            hidden
            multiple
            accept=".pdf,application/pdf"
            :disabled="busy"
            @change="onFileInputChange"
          />
        </label>
      </div>

      <div v-if="message" class="notice" :class="messageTone">{{ message }}</div>

      <section v-if="pendingFiles.length" class="rdo-admin-table-card">
        <header>
          <div>
            <h3>Pré-validação dos documentos</h3>
            <p>
              Nenhum mês de referência é inferido por período, emissão ou data de upload. Se "Mês ref." não
              for localizado, a definição manual é obrigatória.
            </p>
          </div>
        </header>

        <div class="stack">
          <div v-for="file in pendingFiles" :key="file.id" class="surface-body surface">
            <template v-if="file.error || !file.record">
              <div class="flex flex-wrap items-center justify-between gap-3">
                <div class="flex items-start gap-2 text-sm">
                  <AlertTriangle class="mt-0.5 size-4 shrink-0" style="color: #cc5121" />
                  <div>
                    <div class="font-semibold">{{ file.fileName }}</div>
                    <div class="text-xs" style="color: #cc5121">
                      {{ file.error ?? "Falha ao interpretar o arquivo." }}
                    </div>
                  </div>
                </div>
                <Button variant="outline" size="sm" @click="removePending(file.id)">
                  <X class="size-3.5" /> Remover
                </Button>
              </div>
            </template>
            <template v-else>
              <div class="mb-3 flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div class="text-sm font-semibold">{{ file.fileName }}</div>
                  <div class="mt-0.5 text-xs text-muted-foreground">
                    Fonte do mês de referência: {{ file.record.referenceOriginalText ?? "Mês ref. não localizado" }}
                  </div>
                </div>
                <Badge :variant="isPendingRecordValid(file.record) ? 'success' : 'warning'">
                  {{ isPendingRecordValid(file.record) ? "Pronto para importar" : "Revisão obrigatória" }}
                </Badge>
              </div>

              <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div class="flex flex-col gap-1.5">
                  <Label>Unidade</Label>
                  <Input
                    :model-value="file.record.unit"
                    @update:model-value="
                      (value) =>
                        updatePending(file.id, (current) => ({
                          ...current,
                          unit: String(value),
                          unitAdjusted: String(value).trim() !== (current.detectedUnit ?? '').trim(),
                        }))
                    "
                  />
                  <span class="text-[11px] text-muted-foreground">Detectado: {{ file.record.detectedUnit ?? "—" }}</span>
                </div>
                <div class="flex flex-col gap-1.5">
                  <Label>Número do RSO</Label>
                  <Input
                    type="number"
                    min="1"
                    :model-value="file.record.rsoNumero ?? ''"
                    @update:model-value="
                      (value) =>
                        updatePending(file.id, (current) => {
                          const parsed = value === '' ? null : Number(value);
                          return { ...current, rsoNumero: parsed, rsoAdjusted: parsed !== current.detectedRsoNumero };
                        })
                    "
                  />
                  <span class="text-[11px] text-muted-foreground">
                    Detectado: {{ file.record.detectedRsoNumero ?? "—" }}
                  </span>
                </div>
                <div class="flex flex-col gap-1.5">
                  <Label>Mês de referência</Label>
                  <input
                    class="input"
                    type="month"
                    :value="inputMonthValue(file.record)"
                    @change="
                      (event) => {
                        const [y, m] = (event.target as HTMLInputElement).value.split('-');
                        const referenceYear = y ? Number(y) : null;
                        const referenceMonth = m ? Number(m) : null;
                        updatePending(file.id, (current) => {
                          const adjusted =
                            referenceYear !== current.detectedReferenceYear ||
                            referenceMonth !== current.detectedReferenceMonth;
                          return {
                            ...current,
                            referenceYear,
                            referenceMonth,
                            referenceAdjusted: adjusted,
                            referenceSource: adjusted || !current.detectedReferenceYear ? 'MANUAL' : 'PDF_MES_REF',
                          };
                        });
                      }
                    "
                  />
                  <span class="text-[11px] text-muted-foreground">
                    Detectado:
                    {{
                      file.record.detectedReferenceYear && file.record.detectedReferenceMonth
                        ? competenceLabel(file.record.detectedReferenceYear, file.record.detectedReferenceMonth)
                        : "Não identificada"
                    }}
                  </span>
                </div>
              </div>

              <div class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div class="flex flex-col gap-1.5">
                  <Label>Período</Label>
                  <div class="input" style="display: flex; align-items: center">
                    {{ periodLabel(file.record.periodStart, file.record.periodEnd) }}
                  </div>
                </div>
                <div class="flex flex-col gap-1.5">
                  <Label>Emissão</Label>
                  <div class="input" style="display: flex; align-items: center">{{ shortDate(file.record.emissionDate) }}</div>
                </div>
                <div class="flex flex-col gap-1.5">
                  <Label>Execução</Label>
                  <div class="input" style="display: flex; align-items: center">
                    {{ file.record.execucaoFases.length }} fase(s) · {{ file.record.areas.length }} área(s)
                  </div>
                </div>
              </div>

              <div
                v-if="file.record.referenceAdjusted || file.record.unitAdjusted || file.record.rsoAdjusted"
                class="mt-3 notice"
                style="display: flex; align-items: center; gap: 8px"
              >
                <Info class="size-3.5 shrink-0" />
                Ajuste manual rastreado: o valor detectado no PDF será preservado junto do valor usado.
              </div>

              <Button variant="outline" size="sm" class="mt-3" @click="removePending(file.id)">
                <X class="size-3.5" /> Remover arquivo
              </Button>
            </template>
          </div>

          <div class="flex flex-wrap items-center gap-3">
            <Button :disabled="busy || validPendingCount === 0" @click="importPendingFiles">
              <UploadCloud class="size-3.5" /> Importar {{ validPendingCount }} RSO(s)
            </Button>
            <Badge v-if="invalidPendingCount" variant="warning">
              {{ invalidPendingCount }} documento(s) aguardando revisão
            </Badge>
          </div>
        </div>
      </section>

      <div v-if="progress" class="notice">
        <Loader2 class="inline size-3.5 animate-spin" />
        Processando lote {{ progress.currentBatch }}/{{ progress.totalBatches }} — inseridos:
        {{ progress.inserted }} · atualizados: {{ progress.updated }} · ignorados: {{ progress.ignored }} ·
        rejeitados: {{ progress.rejected }}
      </div>

      <section class="rdo-admin-context">
        <div class="rdo-admin-context-head">
          <div>
            <h3>Contexto de publicação</h3>
            <p>
              Período e meta usados no cálculo e na publicação do IDP. A competência efetiva é sempre o RSO
              mais recente dentro do semestre — "Detalhar meses" só restringe a visualização.
            </p>
          </div>
          <div class="rdo-admin-badges">
            <Badge variant="secondary">IDP</Badge>
            <Badge variant="outline">{{ activeDocuments }} RSO(s) ativo(s)</Badge>
            <Badge :variant="isPublished ? 'success' : 'warning'">{{ isPublished ? "Publicado" : "Rascunho" }}</Badge>
          </div>
        </div>

        <div class="rdo-admin-context-grid">
          <PublicationPeriodField
            field-id="idp-period"
            class="rdo-admin-period-field"
            :year="year"
            :semester="semester"
            :period-options="periodOptions"
            :available-periods="availablePeriods"
            :publish-period="cycle"
            :view-filter="viewFilter"
            :years-in-data="years"
            @change="setPeriod"
            @update:view-filter="viewFilter = $event"
            @prepare-next-semester="setPeriod(nextWorkingPeriod(year, semester).year, nextWorkingPeriod(year, semester).semester)"
          >
            <div class="notice" style="display: flex; align-items: center; justify-content: space-between; gap: 8px">
              <strong>Competência efetiva: {{ competenceLabel(selectedYear, selectedMonth) }}</strong>
              <span>{{ activeDocuments }} RSO(s) ativo(s). Nenhuma versão de outro mês é reutilizada.</span>
            </div>
          </PublicationPeriodField>

          <div class="flex flex-col gap-1.5 rdo-admin-target-field">
            <Label for="idp-target">Meta de aderência (%)</Label>
            <Input id="idp-target" v-model.number="threshold" type="number" step="0.01" min="0" max="200" />
            <p class="text-[11px] text-muted-foreground">Meta padrão: 90%.</p>
          </div>
        </div>

        <p v-if="publication" class="rdo-admin-publication-note">
          Já existe uma publicação vigente para este período — v{{ publication.version }}, publicada em
          {{ formatDate(publication.publishedAt, true) }} por {{ publication.publishedBy?.name ?? "sistema" }}.
          Publicar novamente cria uma nova versão.
        </p>

        <div class="rdo-admin-actions">
          <Button variant="outline" size="sm" :disabled="loading" @click="load"><RotateCw :size="14" /> Recalcular</Button>
          <Button variant="outline" size="sm" @click="unitDialogOpen = true">
            <Ban :size="14" /> Ignorar unidades
            <Badge v-if="excludedUnits.length" variant="secondary">{{ excludedUnits.length }}</Badge>
          </Button>
          <Button variant="outline" size="sm" @click="justificationOpen = true"><Sparkles :size="14" /> Justificativa</Button>
          <Button variant="outline" size="sm" @click="exportExcel">Exportar Excel</Button>
          <Button v-if="activeDocuments" variant="outline" size="sm" @click="exportPdf"><FileDown :size="14" /> Exportar PDF</Button>
          <Button v-if="canClear" variant="destructive" size="sm" :disabled="busy || !data?.total" @click="openClearModal">
            <Trash2 :size="14" /> Limpar tudo
          </Button>
          <Button v-if="canPublish" variant="success" size="sm" :disabled="busy || loading || !activeDocuments" @click="publish">
            <Send :size="14" /> Publicar {{ year }} {{ semester }}
          </Button>
        </div>
      </section>

      <section v-if="canPublish" class="rdo-admin-table-card">
        <header>
          <div>
            <h3>Disciplinas desconsideradas</h3>
            <p>As versões continuam armazenadas; a exclusão afeta apenas os cálculos por disciplina.</p>
          </div>
        </header>
        <div class="flex flex-wrap items-start gap-3">
          <textarea v-model="excludedDisciplinesDraft" rows="3" class="input" style="min-width: 320px; flex: 1" />
          <Button variant="outline" size="sm" :disabled="busy" @click="saveExcludedDisciplines">
            <Save class="size-3.5" /> Salvar exclusões
          </Button>
        </div>
      </section>

      <template v-if="!loading && data">
        <details v-if="documents.length" class="rdo-admin-table-card rdo-collapsible">
          <summary>
            <div>
              <h3>Histórico de versões RSO</h3>
              <p>Todos os documentos permanecem no banco. "Em cálculo" marca a maior versão de cada unidade no mês analisado.</p>
            </div>
            <ChevronDown class="rdo-collapsible-chevron" :size="18" />
          </summary>
          <div class="rdo-collapsible-body">
            <div class="table-wrap">
              <table class="data-table rdo-admin-table">
                <thead>
                  <tr>
                    <th>Unidade</th><th>RSO</th><th>Ref.</th><th>Período</th><th>Emissão</th>
                    <th>Origem ref.</th><th>Arquivo</th><th>1ª importação</th><th>Última atualização</th><th>Uso</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="document in documents" :key="String(document.id)">
                    <td>{{ document.unit }}<span v-if="document.unitAdjusted" class="badge info">ajustada</span></td>
                    <td>RSO {{ document.rsoNumero }}<span v-if="document.rsoAdjusted" class="badge info">ajustado</span></td>
                    <td>
                      {{ competenceLabel(Number(document.referenceYear), Number(document.referenceMonth)) }}
                      <span v-if="document.referenceAdjusted" class="badge info">manual</span>
                    </td>
                    <td>{{ periodLabel(document.periodStart, document.periodEnd) }}</td>
                    <td>{{ shortDate(document.emissionDate) }}</td>
                    <td>
                      <div>{{ document.referenceSource === "PDF_MES_REF" ? "Mês ref. do PDF" : "Ajuste manual" }}</div>
                      <div v-if="document.referenceOriginalText" class="text-xs text-muted-foreground">{{ document.referenceOriginalText }}</div>
                    </td>
                    <td class="truncate" style="max-width: 160px" :title="String(document.fileName)">{{ document.fileName }}</td>
                    <td>
                      <div>{{ formatDate(document.createdAt, true) }}</div>
                      <div v-if="document.firstImportedBy" class="text-xs text-muted-foreground">por {{ document.firstImportedBy }}</div>
                    </td>
                    <td>
                      <div>{{ formatDate(document.updatedAt, true) }}</div>
                      <div v-if="document.lastUpdatedBy" class="text-xs text-muted-foreground">por {{ document.lastUpdatedBy }}</div>
                    </td>
                    <td>
                      <span
                        class="badge"
                        :class="document.active ? 'good' : ''"
                      >
                        {{ document.active ? "Em cálculo" : document.sameCompetence ? "Histórico do mês" : "Outro mês" }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </details>

        <div v-if="activeDocuments" class="rdo-admin-metrics">
          <article class="is-good">
            <span>Aderência geral (execução)</span>
            <strong>{{ formatPercent(result.aderenciaGeral, true) }}</strong>
            <small>{{ activeDocuments }} RSO(s) ativo(s)</small>
          </article>
          <article :class="civilAderencia !== null && civilAderencia !== undefined && civilAderencia * 100 >= threshold ? 'is-good' : 'is-warn'">
            <span>Civil</span>
            <strong>{{ civilAderencia === null || civilAderencia === undefined ? "—" : formatPercent(civilAderencia, true) }}</strong>
            <small>Por disciplina</small>
          </article>
          <article :class="mecanicaAderencia !== null && mecanicaAderencia !== undefined && mecanicaAderencia * 100 >= threshold ? 'is-good' : 'is-warn'">
            <span>Mecânica</span>
            <strong>{{ mecanicaAderencia === null || mecanicaAderencia === undefined ? "—" : formatPercent(mecanicaAderencia, true) }}</strong>
            <small>Por disciplina</small>
          </article>
          <article :class="eletricaAderencia !== null && eletricaAderencia !== undefined && eletricaAderencia * 100 >= threshold ? 'is-good' : 'is-warn'">
            <span>Elétrica</span>
            <strong>{{ eletricaAderencia === null || eletricaAderencia === undefined ? "—" : formatPercent(eletricaAderencia, true) }}</strong>
            <small>Por disciplina</small>
          </article>
        </div>

        <section v-if="activeDocuments" class="rdo-admin-table-card">
          <header>
            <div>
              <h3>Execução geral por unidade</h3>
              <p>Fonte: página 1 → Avanços por Etapa → linha Execução → acumulado. A maior versão semanal do mês analisado é usada.</p>
            </div>
          </header>
          <div class="table-wrap">
            <table class="data-table rdo-admin-table">
              <thead>
                <tr>
                  <th style="width: 28px" />
                  <th>Unidade</th><th>RSO utilizado</th><th>Período</th><th>Ref.</th>
                  <th class="numeric">Fases</th><th class="numeric">Prev. acum.</th>
                  <th class="numeric">Real acum.</th><th class="numeric">Aderência</th><th>Situação</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="unit in unitRows" :key="`unit-${unit.unit}`">
                  <tr class="rdo-collapsible-row" style="cursor: pointer" @click="toggle(`unit-${unit.unit}`)">
                    <td>
                      <ChevronRight :size="15" :style="{ transform: expanded.has(`unit-${unit.unit}`) ? 'rotate(90deg)' : 'none', transition: 'transform .15s' }" />
                    </td>
                    <td>{{ formatUnitLabel(String(unit.unit)) }}</td>
                    <td>RSO {{ unit.rsoNumero }}</td>
                    <td>{{ periodLabel(unit.periodStart, unit.periodEnd) }}</td>
                    <td>
                      {{ competenceLabel(Number(unit.referenceYear), Number(unit.referenceMonth)) }}
                      <span v-if="unit.referenceAdjusted" class="badge info">manual</span>
                    </td>
                    <td class="numeric">{{ unit.nFases }}</td>
                    <td class="numeric">{{ accumulated(unit.prevAcum) }}</td>
                    <td class="numeric">{{ accumulated(unit.realAcum) }}</td>
                    <td class="numeric">{{ unit.aderencia === null ? "—" : formatPercent(Number(unit.aderencia) * 100) }}</td>
                    <td>
                      <span class="badge" :class="unit.excluded ? '' : Number(unit.aderencia ?? 0) * 100 >= threshold ? 'good' : 'bad'">
                        {{ unit.excluded ? "Ignorada" : Number(unit.aderencia ?? 0) * 100 >= threshold ? "Dentro da meta" : "Fora da meta" }}
                      </span>
                    </td>
                  </tr>
                  <template v-if="expanded.has(`unit-${unit.unit}`)">
                    <tr v-for="(phase, index) in unit.phases as Array<Record<string, unknown>>" :key="`unit-${unit.unit}-phase-${index}`" class="rdo-collapsible-subrow">
                      <td /><td class="text-muted-foreground">{{ phase.label }}</td><td /><td /><td />
                      <td /><td class="numeric text-muted-foreground">{{ accumulated(phase.prevAcum) }}</td>
                      <td class="numeric text-muted-foreground">{{ accumulated(phase.realAcum) }}</td>
                      <td class="numeric text-muted-foreground">
                        {{ formatPercent(Number(phase.prevAcum) ? (Number(phase.realAcum) / Number(phase.prevAcum)) * 100 : 0) }}
                      </td>
                      <td />
                    </tr>
                  </template>
                </template>
              </tbody>
            </table>
          </div>
        </section>

        <section v-if="activeDocuments" class="rdo-admin-table-card">
          <header>
            <div>
              <h3>Aderência por disciplina</h3>
              <p>Média das áreas do RSO ativo de cada unidade no mês analisado.</p>
            </div>
          </header>
          <div class="table-wrap">
            <table class="data-table rdo-admin-table">
              <thead>
                <tr>
                  <th style="width: 28px" />
                  <th>Disciplina</th><th class="numeric">Unidades</th><th class="numeric">Prev. médio</th>
                  <th class="numeric">Real médio</th><th class="numeric">Aderência</th><th>Situação</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="(row, rowIndex) in disciplineRows" :key="`disc-${rowIndex}`">
                  <tr
                    class="rdo-collapsible-row"
                    :style="{ cursor: (row.unitGroups as unknown[])?.length ? 'pointer' : 'default' }"
                    @click="(row.unitGroups as unknown[])?.length && toggle(`disc-${rowIndex}`)"
                  >
                    <td>
                      <ChevronRight
                        v-if="(row.unitGroups as unknown[])?.length"
                        :size="15"
                        :style="{ transform: expanded.has(`disc-${rowIndex}`) ? 'rotate(90deg)' : 'none', transition: 'transform .15s' }"
                      />
                    </td>
                    <td>{{ row.disciplina }}</td>
                    <td class="numeric">{{ (row.unitGroups as unknown[])?.length ?? 0 }}</td>
                    <td class="numeric">{{ row.prevAvg === null ? "—" : accumulated(row.prevAvg) }}</td>
                    <td class="numeric">{{ row.realAvg === null ? "—" : accumulated(row.realAvg) }}</td>
                    <td class="numeric">{{ row.aderencia === null ? "—" : formatPercent(Number(row.aderencia) * 100) }}</td>
                    <td>
                      <span v-if="row.aderencia === null" class="badge">Sem dados</span>
                      <span v-else class="badge" :class="Number(row.aderencia) * 100 >= threshold ? 'good' : 'bad'">
                        {{ Number(row.aderencia) * 100 >= threshold ? "Dentro da meta" : "Fora da meta" }}
                      </span>
                    </td>
                  </tr>
                  <template v-if="expanded.has(`disc-${rowIndex}`)">
                    <tr
                      v-for="group in row.unitGroups as Array<Record<string, unknown>>"
                      :key="`disc-${rowIndex}-${group.unit}`"
                      class="rdo-collapsible-subrow"
                    >
                      <td />
                      <td class="text-muted-foreground">{{ formatUnitLabel(String(group.unit)) }}</td>
                      <td class="numeric text-muted-foreground">{{ (group.entries as unknown[])?.length ?? 0 }}</td>
                      <td class="numeric text-muted-foreground">{{ accumulated(group.prevAvg) }}</td>
                      <td class="numeric text-muted-foreground">{{ accumulated(group.realAvg) }}</td>
                      <td class="numeric text-muted-foreground">{{ group.aderencia === null ? "—" : formatPercent(Number(group.aderencia) * 100) }}</td>
                      <td />
                    </tr>
                  </template>
                </template>
              </tbody>
            </table>
          </div>
        </section>

        <section v-if="activeDocuments" class="rdo-admin-table-card">
          <header>
            <div>
              <h3>Detalhamento por unidade</h3>
              <p>Expanda as disciplinas para chegar às áreas originais do RSO ativo.</p>
            </div>
            <div class="flex flex-col gap-1.5 rdo-admin-select-field">
              <Label for="idp-unit-detail">Unidade</Label>
              <Select id="idp-unit-detail" v-model="selectedUnit">
                <option v-for="unit in unitRows" :key="String(unit.unit)" :value="unit.unit">
                  {{ formatUnitLabel(String(unit.unit)) }}
                </option>
              </Select>
            </div>
          </header>
          <div class="table-wrap">
            <table class="data-table rdo-admin-table">
              <thead>
                <tr>
                  <th style="width: 28px" />
                  <th>Disciplina / área</th><th class="numeric">Áreas usadas</th>
                  <th class="numeric">Prev. acum.</th><th class="numeric">Real acum.</th><th class="numeric">Aderência</th>
                </tr>
              </thead>
              <tbody>
                <template v-if="(selectedUnitDetail?.disciplines as unknown[])?.length">
                  <template v-for="(discipline, index) in selectedUnitDetail?.disciplines as Array<Record<string, unknown>>" :key="`unit-detail-${index}`">
                    <tr class="rdo-collapsible-row" style="cursor: pointer" @click="toggle(`unit-detail-${index}`)">
                      <td>
                        <ChevronRight :size="15" :style="{ transform: expanded.has(`unit-detail-${index}`) ? 'rotate(90deg)' : 'none', transition: 'transform .15s' }" />
                      </td>
                      <td>{{ discipline.disciplina }}</td>
                      <td class="numeric">{{ (discipline.areas as unknown[])?.length ?? 0 }}</td>
                      <td class="numeric">{{ accumulated(discipline.prevAvg) }}</td>
                      <td class="numeric">{{ accumulated(discipline.realAvg) }}</td>
                      <td class="numeric">{{ discipline.aderencia === null ? "—" : formatPercent(Number(discipline.aderencia) * 100) }}</td>
                    </tr>
                    <template v-if="expanded.has(`unit-detail-${index}`)">
                      <tr
                        v-for="(area, areaIndex) in discipline.areas as Array<Record<string, unknown>>"
                        :key="`unit-detail-${index}-${areaIndex}`"
                        class="rdo-collapsible-subrow"
                      >
                        <td />
                        <td class="text-muted-foreground">{{ area.area }}</td>
                        <td />
                        <td class="numeric text-muted-foreground">{{ accumulated(area.prevAcum) }}</td>
                        <td class="numeric text-muted-foreground">{{ accumulated(area.realAcum) }}</td>
                        <td class="numeric text-muted-foreground">
                          {{ formatPercent(Number(area.prevAcum) ? (Number(area.realAcum) / Number(area.prevAcum)) * 100 : 0) }}
                        </td>
                      </tr>
                    </template>
                  </template>
                </template>
                <tr v-else><td colspan="6" class="empty-cell">Nenhuma disciplina reconhecida para esta unidade.</td></tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>
      <div v-else-if="!loading" class="rdo-admin-empty">
        <span>Aguardando dados</span>
        <strong>IDP</strong>
        <p>Importe RSOs em PDF para visualizar os resultados administrativos.</p>
      </div>
      <div v-if="loading" class="loading-state"><div class="spinner" /></div>
    </div>
  </div>

  <UnitExclusionDialog
    :open="unitDialogOpen"
    :units="unitOptions"
    :excluded="excludedUnits"
    :busy="busy"
    description="Unidades marcadas continuam visíveis no histórico de RSOs, mas ficam de fora da execução geral, das disciplinas e do painel publicado."
    @update:open="unitDialogOpen = $event"
    @save="saveExcludedUnits"
  />

  <ClearRecordsDialog
    :open="clearModalOpen"
    title="Limpar registros do IDP"
    description="Exclui permanentemente os RSOs da base administrativa do IDP no banco de dados. O painel já publicado não é afetado."
    :period-range="clearPeriodRange"
    :years-in-data="years"
    :fetch-affected-count="fetchAffectedCount"
    affected-label="RSO(s) de IDP"
    :busy="busy"
    @update:open="clearModalOpen = $event"
    @update:period-range="clearPeriodRange = $event"
    @confirm="confirmClear"
  />

  <JustificationDialog
    :open="justificationOpen"
    module="idp"
    :year="selectedYear"
    :month="selectedMonth"
    :target="threshold"
    @close="justificationOpen = false"
  />
</template>
