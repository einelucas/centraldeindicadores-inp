<script setup lang="ts">
import { AlertTriangle, Loader2, Trash2 } from "lucide-vue-next";
import type { PeriodRange } from "~/types/api";

const CONFIRM_PHRASE = "deletar dados";

const props = defineProps<{
  open: boolean;
  title: string;
  description: string;
  periodRange: PeriodRange | null;
  yearsInData: readonly number[];
  fetchAffectedCount: (period: PeriodRange | null) => Promise<number>;
  affectedLabel: string;
  busy: boolean;
}>();
const emit = defineEmits<{
  "update:open": [value: boolean];
  "update:periodRange": [value: PeriodRange | null];
  confirm: [];
}>();

const confirmText = ref("");
const count = ref<number | null>(null);
const countLoading = ref(false);
const countError = ref<string | null>(null);
let requestId = 0;

watch(
  () => props.open,
  (open) => {
    if (open) confirmText.value = "";
  },
);
watch(
  () => props.periodRange,
  () => {
    confirmText.value = "";
  },
);

async function loadCount() {
  if (!props.open) return;
  const id = ++requestId;
  count.value = null;
  countError.value = null;
  countLoading.value = true;
  try {
    const next = await props.fetchAffectedCount(props.periodRange);
    if (requestId !== id) return;
    count.value = next;
  } catch (err) {
    if (requestId !== id) return;
    countError.value = err instanceof Error ? err.message : "Falha ao calcular os registros afetados.";
  } finally {
    if (requestId === id) countLoading.value = false;
  }
}

watch([() => props.open, () => props.periodRange], loadCount, { immediate: true });

const canConfirm = computed(
  () => !props.busy && !countLoading.value && count.value !== null && count.value > 0 && confirmText.value.trim() === CONFIRM_PHRASE,
);

function close() {
  if (props.busy) return;
  emit("update:open", false);
}
</script>

<template>
  <Dialog :open="open" @update:open="close">
    <DialogContent class="max-w-lg">
      <DialogHeader>
        <div class="flex items-start gap-3">
          <div class="flex size-9 shrink-0 items-center justify-center rounded-lg bg-danger/10 text-danger">
            <AlertTriangle class="size-5" />
          </div>
          <div>
            <DialogTitle>{{ title }}</DialogTitle>
            <DialogDescription>{{ description }}</DialogDescription>
          </div>
        </div>
        <DialogCloseButton @click="close" />
      </DialogHeader>

      <div class="flex flex-col gap-4 p-5">
        <div class="flex flex-col gap-1.5">
          <Label>Período a excluir</Label>
          <PeriodRangeFilter :model-value="periodRange" :years-in-data="yearsInData" label="" @update:model-value="emit('update:periodRange', $event)" />
        </div>

        <div class="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/5 px-3.5 py-2.5 text-sm font-semibold text-danger">
          <AlertTriangle class="mt-0.5 size-4 shrink-0" />
          <span v-if="countLoading" class="flex items-center gap-1.5 font-medium">
            <Loader2 class="size-3.5 shrink-0 animate-spin" /> Calculando registros afetados…
          </span>
          <span v-else-if="countError">{{ countError }}</span>
          <span v-else-if="count && count > 0">
            {{ count.toLocaleString("pt-BR") }} {{ affectedLabel }} serão apagados permanentemente do banco de dados{{
              periodRange ? " no período selecionado." : " (toda a base)."
            }}
            Essa ação não pode ser desfeita.
          </span>
          <span v-else>Nenhum registro encontrado para o período selecionado.</span>
        </div>

        <div class="flex flex-col gap-1.5">
          <Label for="clearConfirmText">Para confirmar, digite <span class="text-danger">{{ CONFIRM_PHRASE }}</span> abaixo</Label>
          <Input
            id="clearConfirmText"
            v-model="confirmText"
            :placeholder="CONFIRM_PHRASE"
            autocomplete="off"
            :disabled="busy"
            class="border-danger/40 focus-visible:ring-danger/40"
          />
        </div>
      </div>

      <DialogFooter>
        <Button type="button" variant="outline" size="sm" :disabled="busy" @click="close">Cancelar</Button>
        <Button type="button" variant="destructive" size="sm" :disabled="!canConfirm" @click="emit('confirm')">
          <Loader2 v-if="busy" class="size-3.5 animate-spin" />
          <Trash2 v-else class="size-3.5" />
          Excluir permanentemente
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
