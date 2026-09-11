<script setup lang="ts">
import { cycleFromYearSemester, formatPeriodRangeLabel, type Semester } from "~/utils/period";

const props = withDefaults(
  defineProps<{ year: number; semester: Semester; label?: string }>(),
  { label: "Período de publicação" },
);
const emit = defineEmits<{ change: [year: number, semester: Semester] }>();

const currentYear = new Date().getFullYear();
const yearOptions = Array.from({ length: 8 }, (_, index) => currentYear + 2 - index);
const cycle = computed(() => cycleFromYearSemester(props.year, props.semester));

function handleStartYearChange(nextStartYear: number) {
  const nextYear = props.semester === "S1" ? nextStartYear + 1 : nextStartYear;
  emit("change", nextYear, props.semester);
}
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <Label v-if="label">{{ label }}</Label>
    <div class="flex flex-wrap items-end gap-2">
      <div class="flex flex-col gap-1">
        <span class="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Ano inicial</span>
        <Select
          :model-value="cycle.startYear"
          class="w-24"
          aria-label="Ano inicial"
          @change="handleStartYearChange(Number(($event.target as HTMLSelectElement).value))"
        >
          <option v-for="y in yearOptions" :key="y" :value="y">{{ y }}</option>
        </Select>
      </div>

      <div class="flex flex-col gap-1">
        <span class="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Semestre</span>
        <Select
          :model-value="semester"
          class="w-32"
          aria-label="Semestre"
          @change="emit('change', year, ($event.target as HTMLSelectElement).value as Semester)"
        >
          <option value="S2">Jun – Nov</option>
          <option value="S1">Dez – Mai</option>
        </Select>
      </div>

      <div class="flex flex-col gap-1">
        <span class="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Ano final</span>
        <Select
          :model-value="cycle.endYear"
          class="w-24"
          aria-label="Ano final"
          @change="emit('change', Number(($event.target as HTMLSelectElement).value), semester)"
        >
          <option v-for="y in yearOptions" :key="y" :value="y">{{ y }}</option>
        </Select>
      </div>
    </div>
    <p class="text-xs font-medium text-muted-foreground">
      Competência: {{ semester }} {{ year }} · Período: {{ formatPeriodRangeLabel(cycle) }}
    </p>
  </div>
</template>
