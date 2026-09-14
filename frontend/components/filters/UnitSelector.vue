<script setup lang="ts">
import { formatUnitLabel, normalizeUnitCode } from "~/logic/lib/units";

const props = withDefaults(defineProps<{ units?: string[] }>(), {
  units: () => [],
});
const model = defineModel<string>({ required: true });

const options = computed(() => {
  const codes = new Set(
    props.units.map((unit) => normalizeUnitCode(unit)).filter(Boolean),
  );
  return [...codes].sort((a, b) =>
    formatUnitLabel(a).localeCompare(formatUnitLabel(b), "pt-BR"),
  );
});

watch(
  options,
  (next) => {
    if (model.value !== "all" && !next.includes(model.value))
      model.value = "all";
  },
  { immediate: true },
);
</script>

<template>
  <label class="field">
    <span>Unidade</span>
    <select v-model="model" :disabled="!options.length">
      <option value="all">Geral</option>
      <option v-for="unit in options" :key="unit" :value="unit">
        {{ formatUnitLabel(unit) }}
      </option>
    </select>
  </label>
</template>
