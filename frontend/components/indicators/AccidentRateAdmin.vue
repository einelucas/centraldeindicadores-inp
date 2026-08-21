<script setup lang="ts">
import { Plus, RefreshCw, Save, Send, Trash2 } from "lucide-vue-next";
import type { PeriodRange } from "~/types/api";
import { currentOperationalPeriod, MONTHS, periodToQuery } from "~/utils/period";
import { formatNumber } from "~/utils/format";

defineProps<{ canPublish: boolean; canClear: boolean }>();
const api = useApi();
const period = ref<PeriodRange>(currentOperationalPeriod());
const data = ref<Record<string, unknown> | null>(null);
const loading = ref(true), busy = ref(false);
const message = ref(""), tone = ref<"success" | "error">("success");
const target = ref(0), excludedText = ref("");
const monthForm = reactive({ id: "", year: new Date().getFullYear(), month: new Date().getMonth()+1, rate: 0, caf: 0 });
const unitForm = reactive({ id: "", year: new Date().getFullYear(), month: new Date().getMonth()+1, unit: "", saf: 0, caf: 0 });
const clearOpen = ref(false), recordCount = ref(0);
const justificationOpen = ref(false);
const monthly = computed(() => Array.isArray(data.value?.monthly) ? data.value?.monthly as Array<Record<string, unknown>> : []);
const units = computed(() => Array.isArray(data.value?.units) ? data.value?.units as Array<Record<string, unknown>> : []);
const result = computed(() => (data.value?.result as Record<string, unknown>) ?? {});
const excluded = () => excludedText.value.split(/[\n,;]/).map(v => v.trim()).filter(Boolean);
function notify(text: string, kind: "success"|"error"="success") { message.value=text; tone.value=kind; }

async function load() {
  loading.value=true;
  try { const response=await api.get<Record<string,unknown>>("/taxa-acidentes", periodToQuery(period.value)); data.value=response; target.value=Number(response.target ?? 0); excludedText.value=((response.excludedUnits as string[]) ?? []).join("\n"); }
  catch(cause){notify(cause instanceof Error?cause.message:"Erro ao carregar dados.","error");}
  finally{loading.value=false;}
}
async function saveMonth(){busy.value=true;try{await api.post("/taxa-acidentes",{type:"month",...monthForm,id:monthForm.id||null});notify("Lançamento mensal salvo.");Object.assign(monthForm,{id:"",rate:0,caf:0});await load();}catch(cause){notify(cause instanceof Error?cause.message:"Erro ao salvar.","error");}finally{busy.value=false;}}
async function saveUnit(){busy.value=true;try{await api.post("/taxa-acidentes",{type:"unit",...unitForm,id:unitForm.id||null});notify("Lançamento por unidade salvo.");Object.assign(unitForm,{id:"",unit:"",saf:0,caf:0});await load();}catch(cause){notify(cause instanceof Error?cause.message:"Erro ao salvar.","error");}finally{busy.value=false;}}
async function saveSettings(){busy.value=true;try{await api.post("/taxa-acidentes",{type:"settings",target:target.value});await api.patch("/taxa-acidentes",{excludedUnits:excluded()});notify("Configurações salvas.");await load();}catch(cause){notify(cause instanceof Error?cause.message:"Erro ao salvar.","error");}finally{busy.value=false;}}
async function removeMonth(row:Record<string,unknown>){if(!confirm("Excluir este lançamento mensal?"))return;try{await api.delete("/taxa-acidentes",undefined,{kind:"month",year:row.year,month:row.month});await load();}catch(cause){notify(cause instanceof Error?cause.message:"Erro ao excluir.","error");}}
async function removeUnit(row:Record<string,unknown>){if(!confirm("Excluir este lançamento da unidade?"))return;try{await api.delete("/taxa-acidentes",undefined,{kind:"unit",id:row.id});await load();}catch(cause){notify(cause instanceof Error?cause.message:"Erro ao excluir.","error");}}
function editMonth(row:Record<string,unknown>){Object.assign(monthForm,{id:String(row.id),year:Number(row.year),month:Number(row.month),rate:Number(row.rate),caf:Number(row.caf)});}
function editUnit(row:Record<string,unknown>){Object.assign(unitForm,{id:String(row.id),year:Number(row.year),month:Number(row.month),unit:String(row.unit),saf:Number(row.saf),caf:Number(row.caf)});}
async function publish(){busy.value=true;try{await api.post("/publicacoes/taxa-acidentes",periodToQuery(period.value));notify("Painel publicado com sucesso.");}catch(cause){notify(cause instanceof Error?cause.message:"Erro ao publicar.","error");}finally{busy.value=false;}}
async function prepareClear(){try{recordCount.value=(await api.get<{count:number}>("/taxa-acidentes/registros",periodToQuery(period.value))).count;clearOpen.value=true;}catch(cause){notify(cause instanceof Error?cause.message:"Erro ao contar registros.","error");}}
async function clear(all=false){busy.value=true;try{await api.delete("/taxa-acidentes/registros",all?{all:true}:periodToQuery(period.value));clearOpen.value=false;notify("Registros excluídos; publicação preservada.");await load();}catch(cause){notify(cause instanceof Error?cause.message:"Erro ao excluir.","error");}finally{busy.value=false;}}
watch(period,load,{deep:true});onMounted(load);
</script>

<template>
  <div class="stack">
    <section class="surface"><header class="surface-header"><div><h2>Taxa de Acidentes — Administração</h2><p>Lançamentos mensais e por unidade.</p></div><div class="toolbar"><PeriodSelector v-model="period"/><button class="btn btn-icon" @click="load"><RefreshCw :size="16"/></button></div></header>
      <div class="surface-body stack"><div v-if="message" class="notice" :class="tone">{{message}}</div><div class="toolbar"><button v-if="canPublish" class="btn success" :disabled="busy" @click="publish"><Send :size="15"/> Publicar painel</button><button class="btn" @click="justificationOpen=true">Justificativa</button><button v-if="canClear" class="btn danger" @click="prepareClear"><Trash2 :size="15"/> Limpar registros</button></div>
        <div v-if="loading" class="loading-state"><div class="spinner"/></div><template v-else>
          <div class="metric-grid"><MetricCard label="Taxa consolidada" :value="formatNumber(result.result,2)"/><MetricCard label="Meta" :value="formatNumber(result.target,2)"/><MetricCard label="CAF mensal" :value="formatNumber(result.totalCaf)"/><MetricCard label="SAF por unidade" :value="formatNumber(result.totalSaf)"/><MetricCard label="Meses" :value="formatNumber(result.monthsCount)"/></div>
          <section class="surface"><header class="surface-header"><div><h3>Configuração</h3><p>Meta máxima e unidades fora do consolidado.</p></div><button class="btn primary" @click="saveSettings"><Save :size="15"/> Salvar</button></header><div class="surface-body toolbar"><label class="field"><span>Meta de frequência</span><input v-model.number="target" type="number" min="0" step="0.01"/></label><label class="field flex-1"><span>Unidades excluídas</span><textarea v-model="excludedText" rows="3"/></label></div></section>
          <div class="chart-grid"><section class="surface chart-card"><h3>Taxa mensal</h3><p>Taxa de frequência por competência.</p><LineChart :points="(result.monthly as any[] || []).map(row=>({label:row.label,value:row.rate}))" :target="target"/></section><section class="surface chart-card"><h3>Acidentes por unidade</h3><p>Total CAF + SAF.</p><BarChart :points="(result.units as any[] || []).map(row=>({label:row.label,value:Number(row.caf)+Number(row.saf)}))"/></section></div>
        </template>
      </div>
    </section>
    <div class="chart-grid">
      <section class="surface"><header class="surface-header"><div><h3>Lançamento mensal</h3><p>Taxa de frequência e acidentes CAF.</p></div></header><form class="surface-body toolbar" @submit.prevent="saveMonth"><input v-model="monthForm.id" type="hidden"/><label class="field"><span>Ano</span><input v-model.number="monthForm.year" type="number" min="2000" max="2100" required/></label><label class="field"><span>Mês</span><select v-model.number="monthForm.month"><option v-for="(name,index) in MONTHS" :key="name" :value="index+1">{{name}}</option></select></label><label class="field"><span>Taxa</span><input v-model.number="monthForm.rate" type="number" min="0" step="0.01" required/></label><label class="field"><span>CAF</span><input v-model.number="monthForm.caf" type="number" min="0" required/></label><button class="btn primary" :disabled="busy"><Plus :size="15"/> Salvar</button></form></section>
      <section class="surface"><header class="surface-header"><div><h3>Lançamento por unidade</h3><p>Acidentes CAF e SAF.</p></div></header><form class="surface-body toolbar" @submit.prevent="saveUnit"><input v-model="unitForm.id" type="hidden"/><label class="field"><span>Ano</span><input v-model.number="unitForm.year" type="number" min="2000" max="2100" required/></label><label class="field"><span>Mês</span><select v-model.number="unitForm.month"><option v-for="(name,index) in MONTHS" :key="name" :value="index+1">{{name}}</option></select></label><label class="field"><span>Unidade</span><input v-model="unitForm.unit" required/></label><label class="field"><span>CAF</span><input v-model.number="unitForm.caf" type="number" min="0" required/></label><label class="field"><span>SAF</span><input v-model.number="unitForm.saf" type="number" min="0" required/></label><button class="btn primary" :disabled="busy"><Plus :size="15"/> Salvar</button></form></section>
    </div>
    <section class="surface"><header class="surface-header"><div><h3>Histórico mensal</h3></div></header><div class="surface-body"><div class="table-wrap"><table class="data-table"><thead><tr><th>Competência</th><th class="numeric">Taxa</th><th class="numeric">CAF</th><th>Ações</th></tr></thead><tbody><tr v-for="row in monthly" :key="String(row.id)"><td>{{MONTHS[Number(row.month)-1]}}/{{row.year}}</td><td class="numeric">{{formatNumber(row.rate,2)}}</td><td class="numeric">{{row.caf}}</td><td><button class="btn small" @click="editMonth(row)">Editar</button> <button class="btn small danger" @click="removeMonth(row)">Excluir</button></td></tr></tbody></table></div></div></section>
    <section class="surface"><header class="surface-header"><div><h3>Histórico por unidade</h3></div></header><div class="surface-body"><div class="table-wrap"><table class="data-table"><thead><tr><th>Competência</th><th>Unidade</th><th class="numeric">CAF</th><th class="numeric">SAF</th><th>Ações</th></tr></thead><tbody><tr v-for="row in units" :key="String(row.id)"><td>{{MONTHS[Number(row.month)-1]}}/{{row.year}}</td><td>{{row.unit}}</td><td class="numeric">{{row.caf}}</td><td class="numeric">{{row.saf}}</td><td><button class="btn small" @click="editUnit(row)">Editar</button> <button class="btn small danger" @click="removeUnit(row)">Excluir</button></td></tr></tbody></table></div></div></section>
    <AppModal :open="clearOpen" title="Excluir lançamentos" @close="clearOpen=false"><p>Há <strong>{{recordCount}}</strong> lançamentos no período. A publicação atual será preservada.</p><template #actions><button class="btn" @click="clearOpen=false">Cancelar</button><button class="btn danger" @click="clear(false)">Excluir período</button><button class="btn danger" @click="clear(true)">Excluir toda a base</button></template></AppModal>
    <JustificationDialog :open="justificationOpen" module="taxa-acidentes" :year="period.endYear" :month="period.endMonth" :target="target" @close="justificationOpen=false"/>
  </div>
</template>
