<script setup lang="ts">
import { Search } from "lucide-vue-next";
import { formatPeriodRangeLabel } from "~/utils/period";
import type { PeriodRange } from "~/types/api";

const props = withDefaults(
  defineProps<{
    modelValue: PeriodRange | null | undefined;
    yearsInData?: readonly number[];
    publishedLabel: string;
    label?: string;
  }>(),
  { yearsInData: () => [], label: "Consulta" },
);
const emit = defineEmits<{ "update:modelValue": [value: PeriodRange | null | undefined] }>();

const open = ref(false);
const rootRef = ref<HTMLElement | null>(null);
const active = computed(() => props.modelValue !== undefined);

function onClickOutside(event: MouseEvent) {
  if (rootRef.value && !rootRef.value.contains(event.target as Node)) open.value = false;
}
watch(open, (isOpen) => {
  if (isOpen) document.addEventListener("mousedown", onClickOutside);
  else document.removeEventListener("mousedown", onClickOutside);
});
onBeforeUnmount(() => document.removeEventListener("mousedown", onClickOutside));
</script>

<template>
  <div ref="rootRef" class="relative">
    <Button type="button" :variant="active ? 'default' : 'outline'" size="sm" @click="open = !open">
      <Search class="size-3.5" />
      {{ active ? `${label} · ${formatPeriodRangeLabel(modelValue)}` : label }}
    </Button>

    <div v-if="open" class="absolute left-0 top-[calc(100%+6px)] z-30 w-[420px] max-w-[calc(100vw-2rem)] rounded-xl border border-border bg-popover p-3 shadow-lg">
      <p class="mb-2.5 text-xs leading-relaxed text-muted-foreground">
        Filtra só o que aparece aqui na Administração — não muda o que será publicado ({{ publishedLabel }}).
      </p>
      <PeriodRangeFilter :model-value="modelValue ?? null" label="" :years-in-data="yearsInData" @update:model-value="emit('update:modelValue', $event)" />
      <button v-if="active" type="button" class="mt-2.5 text-xs font-semibold text-primary hover:underline" @click="emit('update:modelValue', undefined)">
        Voltar a seguir o período de publicação
      </button>
    </div>
  </div>
</template>
