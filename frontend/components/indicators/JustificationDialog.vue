<script setup lang="ts">
import { Sparkles, Trash2 } from "lucide-vue-next";

const props = defineProps<{ open: boolean; module: string; year: number; month: number; target: number }>();
const emit = defineEmits<{ close: [] }>();
const api = useApi();
const text = ref("");
const suggestion = ref<Record<string, unknown> | null>(null);
const loading = ref(false);
const message = ref("");

async function load() {
  if (!props.open) return;
  loading.value = true; message.value = "";
  try {
    const result = await api.get<{ records: Array<{ text: string }> }>("/justificativas", { module: props.module, year: props.year, month: props.month });
    text.value = result.records[0]?.text ?? "";
  } catch (cause) { message.value = cause instanceof Error ? cause.message : "Erro ao carregar justificativa."; }
  finally { loading.value = false; }
}

async function suggest() {
  loading.value = true; message.value = "";
  try {
    const result = await api.get<{ suggestion: Record<string, unknown> }>("/justificativas/sugestao", { module: props.module, year: props.year, month: props.month, target: props.target });
    suggestion.value = result.suggestion;
    text.value = String(result.suggestion.suggestedText ?? "");
  } catch (cause) { message.value = cause instanceof Error ? cause.message : "Erro ao gerar sugestão."; }
  finally { loading.value = false; }
}

async function save() {
  if (!text.value.trim()) return;
  loading.value = true; message.value = "";
  try {
    await api.put("/justificativas", {
      module: props.module, year: props.year, month: props.month, text: text.value,
      suggestedText: suggestion.value?.suggestedText ?? null,
      result: suggestion.value?.result ?? null, target: suggestion.value?.target ?? props.target,
      status: suggestion.value?.status ?? null, evidence: suggestion.value?.evidence ?? [],
      sourceImport: suggestion.value?.sourceImport ?? null,
    });
    message.value = "Justificativa salva.";
  } catch (cause) { message.value = cause instanceof Error ? cause.message : "Erro ao salvar justificativa."; }
  finally { loading.value = false; }
}

async function remove() {
  if (!confirm("Excluir a justificativa deste mês?")) return;
  loading.value = true;
  try { await api.delete("/justificativas", undefined, { module: props.module, year: props.year, month: props.month }); text.value = ""; suggestion.value = null; message.value = "Justificativa excluída."; }
  catch (cause) { message.value = cause instanceof Error ? cause.message : "Erro ao excluir justificativa."; }
  finally { loading.value = false; }
}

watch(() => props.open, load);
</script>

<template>
  <AppModal :open="open" title="Análise e justificativa" @close="emit('close')">
    <div class="stack">
      <p class="notice">Competência {{ String(month).padStart(2, '0') }}/{{ year }}. A sugestão é recalculada pelo FastAPI a partir dos registros reais.</p>
      <div class="toolbar"><button class="btn" :disabled="loading" @click="suggest"><Sparkles :size="15" /> Gerar sugestão</button><button class="btn danger" :disabled="loading || !text" @click="remove"><Trash2 :size="15" /> Excluir</button></div>
      <label class="field"><span>Justificativa</span><textarea v-model="text" maxlength="10000" placeholder="Descreva causas, impactos e ações." /></label>
      <p v-if="message" class="notice" :class="message.includes('salv') || message.includes('exclu') ? 'success' : ''">{{ message }}</p>
    </div>
    <template #actions><button class="btn" @click="emit('close')">Cancelar</button><button class="btn primary" :disabled="loading || !text.trim()" @click="save">Salvar</button></template>
  </AppModal>
</template>
