<script setup lang="ts">
import { RefreshCw, Save } from "lucide-vue-next";
interface Setting {key:string;value:unknown;updatedAt:string;draft:string}
const api=useApi();const items=ref<Setting[]>([]),loading=ref(true),busy=ref(false),message=ref("");
function serialize(value:unknown){return typeof value==="string"?value:JSON.stringify(value,null,2)}
function parse(value:string){try{return JSON.parse(value)}catch{return value}}
async function load(){loading.value=true;try{items.value=(await api.get<{items:Array<Omit<Setting,"draft">>}>("/configuracoes")).items.map(item=>({...item,draft:serialize(item.value)}));}catch(cause){message.value=cause instanceof Error?cause.message:"Erro ao carregar configurações.";}finally{loading.value=false;}}
async function save(item:Setting){busy.value=true;try{await api.patch("/configuracoes",{key:item.key,value:parse(item.draft)});message.value=`${item.key} atualizada.`;await load();}catch(cause){message.value=cause instanceof Error?cause.message:"Erro ao salvar configuração.";}finally{busy.value=false;}}
onMounted(load);
</script>
<template><section class="surface"><header class="surface-header"><div><h2>Configurações</h2><p>Metas e listas globais utilizadas pelos módulos.</p></div><button class="btn btn-icon" @click="load"><RefreshCw :size="16"/></button></header><div class="surface-body stack"><p v-if="message" class="notice">{{message}}</p><div v-if="loading" class="loading-state"><div class="spinner"/></div><div v-else class="table-wrap"><table class="data-table"><thead><tr><th>Chave</th><th>Valor</th><th>Ação</th></tr></thead><tbody><tr v-for="item in items" :key="item.key"><td><code>{{item.key}}</code></td><td><textarea v-model="item.draft" class="input min-h-20"/></td><td><button class="btn primary small" :disabled="busy" @click="save(item)"><Save :size="14"/> Salvar</button></td></tr></tbody></table></div></div></section></template>
