<script setup lang="ts">
import { CalendarRange, FilterX } from "lucide-vue-next";
import { MONTH_NAMES_FULL } from "~/utils/dates";
import { formatPeriodRangeLabel, getCurrentCycle, normalizePeriodRange } from "~/utils/period";
import type { PeriodRange } from "~/types/api";

const props = withDefaults(
  defineProps<{
    modelValue: PeriodRange | null;
    yearsInData?: readonly number[];
    showQuickActions?: boolean;
    allowClear?: boolean;
    label?: string;
  }>(),
  { yearsInData: () => [], showQuickActions: true, allowClear: true, label: "Período" },
);
const emit = defineEmits<{ "update:modelValue": [value: PeriodRange | null] }>();

const showLabel = computed(() => props.label !== "");
const draft = computed(() => props.modelValue ?? getCurrentCycle());
const currentYear = new Date().getFullYear();
const yearOptions = computed(() =>
  Array.from(
    new Set([...props.yearsInData, draft.value.startYear, draft.value.endYear, currentYear - 1, currentYear, currentYear + 1]),
  ).sort((a, b) => a - b),
);

function update(next: Partial<PeriodRange>) {
  emit("update:modelValue", normalizePeriodRange({ ...draft.value, ...next }));
}

</script>

<template>
  <div class="flex flex-col gap-1.5">
    <Label v-if="showLabel">{{ label }}</Label>
    <div class="flex flex-wrap items-end gap-2 rounded-lg border border-border bg-muted/20 p-2">
      <div class="flex flex-col gap-1.5">
        <span class="text-[11px] font-bold uppercase tracking-wide text-muted-foreground">De</span>
        <div class="flex gap-1.5">
          <Select
            :model-value="draft.startMonth"
            class="w-28"
            @change="update({ startMonth: Number(($event.target as HTMLSelectElement).value) })"
          >
            <option v-for="(month, index) in MONTH_NAMES_FULL" :key="month" :value="index + 1">{{ month }}</option>
          </Select>
          <Select
            :model-value="draft.startYear"
            class="w-20"
            @change="update({ startYear: Number(($event.target as HTMLSelectElement).value) })"
          >
            <option v-for="year in yearOptions" :key="year" :value="year">{{ year }}</option>
          </Select>
        </div>
      </div>

      <div class="flex flex-col gap-1.5">
        <span class="text-[11px] font-bold uppercase tracking-wide text-muted-foreground">Até</span>
        <div class="flex gap-1.5">
          <Select
            :model-value="draft.endMonth"
            class="w-28"
            @change="update({ endMonth: Number(($event.target as HTMLSelectElement).value) })"
          >
            <option v-for="(month, index) in MONTH_NAMES_FULL" :key="month" :value="index + 1">{{ month }}</option>
          </Select>
          <Select
            :model-value="draft.endYear"
            class="w-20"
            @change="update({ endYear: Number(($event.target as HTMLSelectElement).value) })"
          >
            <option v-for="year in yearOptions" :key="year" :value="year">{{ year }}</option>
          </Select>
        </div>
      </div>

      <div v-if="showQuickActions" class="flex gap-1.5">
        <Button type="button" variant="outline" size="sm" @click="emit('update:modelValue', getCurrentCycle())">
          <CalendarRange class="size-3.5" /> Ciclo atual
        </Button>
        <Button v-if="allowClear && modelValue" type="button" variant="outline" size="sm" @click="emit('update:modelValue', null)">
          <FilterX class="size-3.5" /> Tudo
        </Button>
      </div>

      <Badge :variant="modelValue ? 'outline' : 'secondary'" class="mb-1">{{ formatPeriodRangeLabel(modelValue) }}</Badge>
    </div>
  </div>
</template>
