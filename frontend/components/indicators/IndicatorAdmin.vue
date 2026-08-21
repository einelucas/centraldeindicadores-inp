<script setup lang="ts">
import { FileUp, RefreshCw, Save, Send, Settings, Sparkles, Trash2 } from "lucide-vue-next";
import type { PeriodRange } from "~/types/api";
import { currentOperationalPeriod, MONTHS, periodToQuery } from "~/utils/period";
import { formatDate, formatNumber, formatPercent } from "~/utils/format";

type ModuleName = "rdo" | "idp" | "rnc" | "cinco-s";
const props = defineProps<{ module: ModuleName; canPublish: boolean; canClear: boolean }>();
const api = useApi();
const imports = useImports();
const exporter = useExport();
const auth = useAuthStore();

const CONFIG = {
  rdo: { title: "RDO — Administração", accept: ".xlsx,.xls,.csv", target: 76 },
  idp: { title: "IDP — Administração", accept: ".pdf", target: 90 },
  rnc: { title: "RNC — Administração", accept: ".xlsx,.xls,.csv", target: 15 },
  "cinco-s": { title: "5S — Administração", accept: ".xlsx,.xls", target: 95 },
} as const;
const config = computed(() => CONFIG[props.module]);
const period = ref<PeriodRange>(currentOperationalPeriod());
const data = ref<Record<string, unknown> | null>(null);
const loading = ref(true);
const busy = ref(false);
const message = ref("");
const messageTone = ref<"success" | "error" | "">("");
const selectedFiles = ref<File[]>([]);
const parsedRecords = ref<Array<Record<string, unknown>>>([]);
const parseErrors = ref<string[]>([]);
const duplicates = ref(0);
const target = ref<number>(config.value.target);
const excludedUnitsText = ref("");
const excludedDisciplinesText = ref("");
const importModal = ref(false);
const clearModal = ref(false);
const recordCount = ref<number | null>(null);
const justificationOpen = ref(false);
const justificationYear = ref(new Date().getFullYear());
const justificationMonth = ref(new Date().getMonth() + 1);
const filters = reactive({ q: "", unidade: "", status: "" });

const result = computed<Record<string, unknown>>(() => (data.value?.result as Record<string, unknown>) ?? {});
const list = (key: string) => Array.isArray(result.value[key]) ? result.value[key] as Array<Record<string, unknown>> : [];
const details = computed(() => Array.isArray(data.value?.detalhe) ? data.value?.detalhe as Array<Record<string, unknown>> : []);
const documents = computed(() => Array.isArray(data.value?.documents) ? data.value?.documents as Array<Record<string, unknown>> : []);
const filteredDetails = computed(() => details.value.filter(row => {
  const text = JSON.stringify(row).toLocaleLowerCase("pt-BR");
  return (!filters.q || text.includes(filters.q.toLocaleLowerCase("pt-BR"))) && (!filters.unidade || row.unidade === filters.unidade) && (!filters.status || row.status === filters.status);
}));

const metrics = computed<Array<[string, string]>>(() => {
  const r = result.value;
  if (props.module === "rdo") return [
    ["RDOs emitidos", formatNumber(r.totalEmitidos)], ["Aprovados", formatNumber(r.totalAprovados)],
    ["Aderência média", formatPercent(Number(r.unitAvg ?? 0) * 100)], ["Em revisão", formatNumber(r.totalRevisar)],
  ];
  if (props.module === "rnc") return [
    ["RNCs criadas", formatNumber(r.totalCriadas)], ["Tratadas", formatNumber(r.totalTratadas)],
    ["Aderência", formatPercent(Number(r.aderenciaTotal ?? 0) * 100)], ["Prazo médio", `${formatNumber(r.resultadoDias, 1)} dias`],
  ];
  if (props.module === "cinco-s") return [
    ["Aderência geral", formatPercent(Number(r.geral ?? 0) * 100)], ["Meta", formatPercent(Number(r.threshold ?? 0) * 100)],
    ["Unidades", formatNumber(r.unitsCount)], ["Meses", formatNumber(r.monthsCount)],
  ];
  return [
    ["Documentos ativos", formatNumber(r.activeDocuments)], ["Aderência geral", formatPercent(Number(r.aderenciaGeral ?? 0) * 100)],
    ["Previsto médio", formatNumber(r.totalPrevistoMedio, 2)], ["Real médio", formatNumber(r.totalRealMedio, 2)],
  ];
});

function showMessage(text: string, tone: "success" | "error" = "success") { message.value = text; messageTone.value = tone; }
function excludedUnits(): string[] { return excludedUnitsText.value.split(/[\n,;]/).map(v => v.trim()).filter(Boolean); }
function excludedDisciplines(): string[] { return excludedDisciplinesText.value.split(/\n/).map(v => v.trim()).filter(Boolean); }

async function load() {
  loading.value = true; message.value = "";
  try {
    const query: Record<string, unknown> = { ...periodToQuery(period.value) };
    data.value = await api.get<Record<string, unknown>>(`/${props.module}`, query);
    target.value = Number(data.value.threshold ?? data.value.metaDias ?? result.value.threshold ?? result.value.metaDias ?? config.value.target);
    excludedUnitsText.value = ((result.value.excludedUnits as string[] | undefined) ?? (data.value.excludedUnits as string[] | undefined) ?? []).join("\n");
    excludedDisciplinesText.value = ((result.value.excludedDisciplines as string[] | undefined) ?? (data.value.excludedDisciplines as string[] | undefined) ?? []).join("\n");
  } catch (cause) { showMessage(cause instanceof Error ? cause.message : "Erro ao carregar dados.", "error"); }
  finally { loading.value = false; }
}

async function selectFiles(event: Event) {
  const input = event.target as HTMLInputElement;
  selectedFiles.value = Array.from(input.files ?? []);
  if (!selectedFiles.value.length) return;
  busy.value = true; parseErrors.value = [];
  try {
    const parsed = await imports.parse(props.module, selectedFiles.value);
    parsedRecords.value = parsed.records;
    parseErrors.value = parsed.errors;
    duplicates.value = parsed.duplicates;
    importModal.value = true;
  } catch (cause) { showMessage(cause instanceof Error ? cause.message : "Erro ao ler arquivo.", "error"); }
  finally { busy.value = false; input.value = ""; }
}

function normalizeIdpRecord(row: Record<string, unknown>) {
  if (props.module !== "idp") return row;
  if (!Number(row.rsoNumero) || !Number(row.referenceYear) || !Number(row.referenceMonth)) throw new Error("Confirme unidade, número do RSO e competência em todos os PDFs.");
  return {
    ...row,
    rsoNumero: Number(row.rsoNumero), referenceYear: Number(row.referenceYear), referenceMonth: Number(row.referenceMonth),
    referenceSource: row.referenceSource === "UNRESOLVED" ? "MANUAL" : row.referenceSource,
    referenceAdjusted: row.referenceSource === "UNRESOLVED" ? true : row.referenceAdjusted,
  };
}

async function runImport() {
  busy.value = true;
  try {
    const records = parsedRecords.value.map(normalizeIdpRecord);
    const outcome = await imports.send(props.module, selectedFiles.value.map(file => file.name).join(", "), records);
    showMessage(`Importação concluída: ${outcome.totals.inserted} inseridos, ${outcome.totals.updated} atualizados, ${outcome.totals.ignored} ignorados e ${outcome.totals.rejected} rejeitados.`);
    importModal.value = false; parsedRecords.value = []; await load();
  } catch (cause) { showMessage(cause instanceof Error ? cause.message : "Erro durante a importação.", "error"); }
  finally { busy.value = false; }
}

async function saveSettings() {
  busy.value = true;
  try {
    if (props.module === "cinco-s") await api.patch("/cinco-s", { target: target.value, excludedUnits: excludedUnits() });
    else if (props.module === "idp") {
      await api.patch("/configuracoes", { key: "idp.target", value: target.value });
      await api.patch("/configuracoes", { key: "idp.excludedUnits", value: excludedUnits() });
      await api.patch("/configuracoes", { key: "idp.excludedDisciplines", value: excludedDisciplines() });
    } else await api.patch(`/${props.module}`, { excludedUnits: excludedUnits() });
    showMessage("Configurações salvas e indicador recalculado."); await load();
  } catch (cause) { showMessage(cause instanceof Error ? cause.message : "Erro ao salvar configuração.", "error"); }
  finally { busy.value = false; }
}

async function publish() {
  busy.value = true;
  try {
    const base = periodToQuery(period.value);
    const body = props.module === "rdo" ? { ...base, threshold: target.value }
      : props.module === "rnc" ? { ...base, metaDias: target.value }
      : props.module === "cinco-s" ? { ...base, target: target.value, excludedUnits: excludedUnits() }
      : { ...base, threshold: target.value };
    await api.post(`/publicacoes/${props.module}`, body);
    showMessage("Painel publicado com sucesso.");
  } catch (cause) { showMessage(cause instanceof Error ? cause.message : "Erro ao publicar.", "error"); }
  finally { busy.value = false; }
}

async function prepareClear() {
  try { recordCount.value = (await api.get<{ count: number }>(`/${props.module}/registros`, periodToQuery(period.value))).count; clearModal.value = true; }
  catch (cause) { showMessage(cause instanceof Error ? cause.message : "Erro ao contar registros.", "error"); }
}

async function clearRecords(all = false) {
  busy.value = true;
  try {
    await api.delete(`/${props.module}/registros`, all ? { all: true } : periodToQuery(period.value));
    clearModal.value = false; showMessage("Registros excluídos. A publicação vigente foi preservada."); await load();
  } catch (cause) { showMessage(cause instanceof Error ? cause.message : "Erro ao excluir registros.", "error"); }
  finally { busy.value = false; }
}

async function editRdoStatus(row: Record<string, unknown>, status: string) {
  try { await api.patch("/rdo/registros", { id: row.id, status }); row.status = status; showMessage("Status atualizado."); }
  catch (cause) { showMessage(cause instanceof Error ? cause.message : "Erro ao editar status.", "error"); }
}

function exportCurrent(kind: "excel" | "pdf") {
  const rows = props.module === "rdo" ? filteredDetails.value : props.module === "idp" ? documents.value : list(props.module === "cinco-s" ? "unitMonths" : "units");
  if (kind === "excel") exporter.excel(`${props.module}-administracao`, rows);
  else exporter.pdf(`${props.module}-administracao`, config.value.title, rows);
}

watch(period, load, { deep: true });
watch(() => props.module, load);
onMounted(load);
</script>

<template>
  <div class="stack">
    <section class="surface">
      <header class="surface-header"><div><h2>{{ config.title }}</h2><p>Dados administrativos calculados pelo FastAPI.</p></div>
        <div class="toolbar"><PeriodSelector v-model="period" /><button class="btn btn-icon" :disabled="loading" @click="load"><RefreshCw :size="16" /></button></div>
      </header>
      <div class="surface-body stack">
        <div v-if="message" class="notice" :class="messageTone">{{ message }}</div>
        <div class="toolbar">
          <label class="btn primary"><FileUp :size="16" /> {{ busy ? 'Processando…' : 'Selecionar arquivos' }}<input type="file" hidden multiple :accept="config.accept" :disabled="busy" @change="selectFiles" /></label>
          <button v-if="canPublish" class="btn success" :disabled="busy || loading" @click="publish"><Send :size="16" /> Publicar painel</button>
          <button class="btn" @click="exportCurrent('excel')">Exportar Excel</button><button class="btn" @click="exportCurrent('pdf')">Exportar PDF</button>
          <button class="btn" @click="justificationOpen = true"><Sparkles :size="15" /> Justificativa</button>
          <button v-if="canClear" class="btn danger" :disabled="busy" @click="prepareClear"><Trash2 :size="15" /> Limpar registros</button>
        </div>
        <div v-if="loading" class="loading-state"><div class="spinner" /></div>
        <template v-else-if="data">
          <div class="metric-grid"><MetricCard v-for="metric in metrics" :key="metric[0]" :label="metric[0]" :value="metric[1]" /></div>

          <section class="surface">
            <header class="surface-header"><div><h3><Settings :size="16" class="inline" /> Configuração</h3><p>Metas e exclusões aplicadas no backend.</p></div><button class="btn primary" :disabled="busy" @click="saveSettings"><Save :size="15" /> Salvar</button></header>
            <div class="surface-body toolbar">
              <label class="field"><span>{{ module === 'rnc' ? 'Meta máxima (dias)' : 'Meta (%)' }}</span><input v-model.number="target" type="number" step="0.01" min="0" /></label>
              <label class="field flex-1"><span>Unidades excluídas (uma por linha)</span><textarea v-model="excludedUnitsText" rows="3" /></label>
              <label v-if="module === 'idp'" class="field flex-1"><span>Disciplinas excluídas (uma por linha)</span><textarea v-model="excludedDisciplinesText" rows="3" /></label>
            </div>
          </section>

          <template v-if="module === 'rdo'">
            <div class="surface-body toolbar surface"><label class="field"><span>Busca</span><input v-model="filters.q" placeholder="ID, grupo ou disciplina" /></label><label class="field"><span>Unidade</span><select v-model="filters.unidade"><option value="">Todas</option><option v-for="unit in (data.filtros as any)?.unidades || []" :key="unit">{{ unit }}</option></select></label><label class="field"><span>Status</span><select v-model="filters.status"><option value="">Todos</option><option v-for="status in (data.filtros as any)?.status || []" :key="status">{{ status }}</option></select></label></div>
            <div class="table-wrap"><table class="data-table"><thead><tr><th>Data</th><th>Unidade</th><th>Grupo</th><th>Disciplina</th><th>Status</th><th>ID</th></tr></thead><tbody><tr v-for="row in filteredDetails" :key="String(row.id)"><td>{{ formatDate(row.data) }}</td><td>{{ row.unidade }}</td><td>{{ row.grupo || '—' }}</td><td>{{ row.disciplina || '—' }}</td><td><select v-if="auth.isAdmin" class="input" :value="row.status" @change="editRdoStatus(row, ($event.target as HTMLSelectElement).value)"><option>Aprovado</option><option>Revisar Relatório</option><option>Preenchendo Relatório</option></select><span v-else>{{ row.status }}</span></td><td>{{ row.relatorioId || '—' }}</td></tr></tbody></table></div>
          </template>

          <template v-else-if="module === 'rnc'">
            <div class="chart-grid"><section class="surface chart-card"><h3>Prazo médio mensal</h3><p>Dias de tratativa por competência.</p><LineChart :points="list('months').map(row => ({label: String(row.label), value: typeof row.diasMedios === 'number' ? row.diasMedios : null}))" :target="target" /></section><section class="surface chart-card"><h3>Aderência por unidade</h3><p>Percentual de RNCs tratadas.</p><BarChart :points="list('units').map(row => ({label: String(row.name), value: Number(row.aderencia || 0)*100}))" suffix="%" /></section></div>
            <div class="table-wrap"><table class="data-table"><thead><tr><th>Unidade</th><th class="numeric">Criadas</th><th class="numeric">Tratadas</th><th class="numeric">Aderência</th><th class="numeric">Dias médios</th><th>Principal ofensor</th></tr></thead><tbody><tr v-for="row in list('units')" :key="String(row.name)"><td>{{ row.name }} <span v-if="row.excluded" class="badge">Excluída</span></td><td class="numeric">{{ row.criadas }}</td><td class="numeric">{{ row.tratadas }}</td><td class="numeric">{{ formatPercent(Number(row.aderencia)*100) }}</td><td class="numeric">{{ formatNumber(row.diasMedios,1) }}</td><td>{{ row.principalOfensor || '—' }}</td></tr></tbody></table></div>
          </template>

          <template v-else-if="module === 'cinco-s'">
            <div class="chart-grid"><section class="surface chart-card"><h3>Evolução mensal</h3><p>Aderência geral do programa.</p><LineChart :points="list('months').map(row => ({label: String(row.label), value: typeof row.geral === 'number' ? row.geral*100 : null}))" :target="target" suffix="%" /></section><section class="surface chart-card"><h3>Unidades no último período</h3><p>Aderência por unidade.</p><BarChart :points="list('unitMonths').slice(-20).map(row => ({label: String(row.unit), value: Number(row.aderencia||0)*100}))" :target="target" suffix="%" /></section></div>
            <div class="table-wrap"><table class="data-table"><thead><tr><th>Unidade</th><th>Competência</th><th class="numeric">Aderência</th><th class="numeric">Áreas</th><th>Status</th></tr></thead><tbody><tr v-for="row in list('unitMonths')" :key="`${row.unit}-${row.year}-${row.month}`"><td>{{ row.unit }}</td><td>{{ MONTHS[Number(row.month)-1] }}/{{ row.year }}</td><td class="numeric">{{ formatPercent(Number(row.aderencia)*100) }}</td><td class="numeric">{{ (row.areas as unknown[])?.length || 0 }}</td><td><span class="badge" :class="row.excluded ? '' : Number(row.aderencia)*100 >= target ? 'good':'bad'">{{ row.excluded ? 'Excluída':'Incluída' }}</span></td></tr></tbody></table></div>
          </template>

          <template v-else>
            <div class="chart-grid"><section class="surface chart-card"><h3>Evolução mensal</h3><p>Aderência do cronograma.</p><LineChart :points="list('monthly').map(row => ({label: String(row.label), value: typeof row.aderencia === 'number' ? row.aderencia*100 : null}))" :target="target" suffix="%" /></section><section class="surface chart-card"><h3>Aderência por disciplina</h3><p>Previsto versus realizado.</p><BarChart :points="list('disciplineRows').map(row => ({label: String(row.disciplina), value: typeof row.aderencia === 'number' ? row.aderencia*100 : null}))" :target="target" suffix="%" /></section></div>
            <div class="table-wrap"><table class="data-table"><thead><tr><th>Unidade</th><th>RSO</th><th>Competência</th><th>Arquivo</th><th class="numeric">Previsto</th><th class="numeric">Real</th><th class="numeric">Aderência</th></tr></thead><tbody><tr v-for="row in list('unitRows')" :key="`${row.unit}-${row.rsoNumero}`"><td>{{ row.unit }} <span v-if="row.excluded" class="badge">Excluída</span></td><td>{{ row.rsoNumero }}</td><td>{{ MONTHS[Number(row.referenceMonth)-1] }}/{{ row.referenceYear }}</td><td>{{ row.fileName }}</td><td class="numeric">{{ formatNumber(row.prevAcum,2) }}</td><td class="numeric">{{ formatNumber(row.realAcum,2) }}</td><td class="numeric">{{ formatPercent(Number(row.aderencia)*100) }}</td></tr></tbody></table></div>
          </template>
        </template>
      </div>
    </section>

    <AppModal :open="importModal" title="Revisar importação" @close="importModal = false">
      <div class="stack"><p class="notice">{{ parsedRecords.length }} registros prontos; {{ duplicates }} duplicatas locais ignoradas.</p><p v-for="error in parseErrors" :key="error" class="notice error">{{ error }}</p>
        <div v-if="module === 'idp'" class="stack"><div v-for="(row,index) in parsedRecords" :key="index" class="surface-body surface"><strong>{{ row.fileName }}</strong><div class="toolbar mt-3"><label class="field"><span>Unidade</span><input v-model="row.unit" /></label><label class="field"><span>RSO</span><input v-model.number="row.rsoNumero" type="number" /></label><label class="field"><span>Ano referência</span><input v-model.number="row.referenceYear" type="number" /></label><label class="field"><span>Mês referência</span><input v-model.number="row.referenceMonth" type="number" min="1" max="12" /></label></div></div></div>
        <div v-else class="table-wrap"><table class="data-table"><thead><tr><th>Prévia</th></tr></thead><tbody><tr v-for="(row,index) in parsedRecords.slice(0,10)" :key="index"><td><code>{{ JSON.stringify(row).slice(0,500) }}</code></td></tr></tbody></table></div>
      </div>
      <template #actions><button class="btn" @click="importModal=false">Cancelar</button><button class="btn primary" :disabled="busy || !parsedRecords.length" @click="runImport"><FileUp :size="15" /> Importar {{ parsedRecords.length }} registros</button></template>
    </AppModal>

    <AppModal :open="clearModal" title="Excluir registros administrativos" @close="clearModal=false"><p>O período selecionado contém <strong>{{ recordCount }}</strong> registros. A publicação vigente não será apagada.</p><template #actions><button class="btn" @click="clearModal=false">Cancelar</button><button class="btn danger" :disabled="busy" @click="clearRecords(false)"><Trash2 :size="15" /> Excluir período</button><button class="btn danger" :disabled="busy" @click="clearRecords(true)">Excluir toda a base</button></template></AppModal>
    <JustificationDialog :open="justificationOpen" :module="module" :year="justificationYear" :month="justificationMonth" :target="target" @close="justificationOpen=false" />
  </div>
</template>
