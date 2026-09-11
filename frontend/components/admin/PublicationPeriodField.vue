<script setup lang="ts">
import { CalendarPlus } from "lucide-vue-next";
import { formatPeriodOptionLabel, type Semester } from "~/utils/period";
import { periodOptionKey, type PeriodOption } from "~/composables/usePublicationPeriodOptions";
import type { PeriodRange } from "~/types/api";

const props = defineProps<{
  fieldId: string;
  year: number;
  semester: Semester;
  periodOptions: PeriodOption[];
  availablePeriods: PeriodOption[];
  publishPeriod: PeriodRange;
  /** Omita viewFilter/onViewFilterChange quando o módulo não tiver filtro de
   * visualização independente (ex.: Scorecard) — o botão some. */
  viewFilter?: PeriodRange | null | undefined;
  yearsInData?: readonly number[];
}>();

const emit = defineEmits<{
  change: [year: number, semester: Semester];
  "update:viewFilter": [value: PeriodRange | null | undefined];
  prepareNextSemester: [];
}>();

const hasViewFilter = computed(() => props.viewFilter !== undefined || "viewFilter" in props);

const viewFilterOutsideWorkingPeriod = computed(() => {
  const vf = props.viewFilter;
  if (!vf) return false;
  return (
    vf.startYear !== props.publishPeriod.startYear ||
    vf.startMonth !== props.publishPeriod.startMonth ||
    vf.endYear !== props.publishPeriod.endYear ||
    vf.endMonth !== props.publishPeriod.endMonth
  );
});

function onSelectChange(event: Event) {
  const [nextYearText, nextSemesterText] = (event.target as HTMLSelectElement).value.split(":");
  if (!nextYearText || !nextSemesterText) return;
  emit("change", Number(nextYearText), nextSemesterText as Semester);
}
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <Label :for="fieldId">Período de trabalho</Label>
    <Select :id="fieldId" :model-value="periodOptionKey(year, semester)" @change="onSelectChange">
      <option v-for="option in periodOptions" :key="periodOptionKey(option.year, option.semester)" :value="periodOptionKey(option.year, option.semester)">
        {{ formatPeriodOptionLabel(option.year, option.semester) }}{{ availablePeriods.some((i) => i.year === option.year && i.semester === option.semester) ? "" : " · Sem dados" }}
      </option>
    </Select>
    <div class="flex flex-wrap items-center gap-2">
      <Button type="button" variant="ghost" size="sm" class="h-auto px-1.5 py-1 text-xs text-muted-foreground" @click="emit('prepareNextSemester')">
        <CalendarPlus class="size-3.5" /> Preparar próximo semestre
      </Button>
      <ViewFilterPopover
        v-if="hasViewFilter"
        :model-value="viewFilter"
        :years-in-data="yearsInData"
        :published-label="formatPeriodOptionLabel(year, semester)"
        label="Detalhar meses"
        @update:model-value="emit('update:viewFilter', $event)"
      />
    </div>
    <p v-if="viewFilterOutsideWorkingPeriod" class="text-xs font-medium text-accent-foreground">
      "Detalhar meses" está fora do período de trabalho ({{ formatPeriodOptionLabel(year, semester) }}) — isso só restringe a
      tabela abaixo; a publicação sempre usa o período de trabalho.
    </p>
    <slot />
  </div>
</template>
