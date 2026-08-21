<script setup lang="ts">
import type { AvailablePeriod, PeriodRange } from "~/types/api";
import { currentOperationalPeriod, operationalPeriod, periodFromAvailable } from "~/utils/period";

const model = defineModel<PeriodRange>({ required: true });
const props = withDefaults(defineProps<{ allowAll?: boolean }>(), { allowAll: false });
const api = useApi();
const periods = ref<AvailablePeriod[]>([]);
const selected = ref("");
const now = new Date();
const fallbackYears = Array.from({ length: 8 }, (_, index) => now.getFullYear() + 2 - index);

function same(a: PeriodRange, b: PeriodRange) {
  return a.startYear === b.startYear && a.startMonth === b.startMonth && a.endYear === b.endYear && a.endMonth === b.endMonth;
}

function syncSelection() {
  const found = periods.value.find((item) => same(periodFromAvailable(item), model.value));
  if (found) selected.value = found.periodKey;
  else {
    const semester = model.value.startMonth === 12 ? "S1" : "S2";
    const year = semester === "S1" ? model.value.endYear : model.value.startYear;
    selected.value = `${year}-${semester}`;
  }
}

function update() {
  if (selected.value === "all" && props.allowAll) return;
  const found = periods.value.find((item) => item.periodKey === selected.value);
  if (found) model.value = periodFromAvailable(found);
  else {
    const [yearText, semesterText] = selected.value.split("-");
    model.value = operationalPeriod(Number(yearText), semesterText as "S1" | "S2");
  }
}

onMounted(async () => {
  try {
    periods.value = (await api.get<{ periods: AvailablePeriod[] }>("/available-periods")).periods;
  } catch { periods.value = []; }
  if (!model.value) model.value = currentOperationalPeriod();
  syncSelection();
});
watch(model, syncSelection, { deep: true });
</script>

<template>
  <label class="field">
    <span>Período operacional</span>
    <select v-model="selected" @change="update">
      <option v-if="allowAll" value="all">Todos</option>
      <option v-for="item in periods" :key="item.periodKey" :value="item.periodKey">{{ item.label }}</option>
      <template v-if="!periods.length">
        <template v-for="year in fallbackYears" :key="year">
          <option :value="`${year}-S1`">S1 {{ year }} · Dez/{{ year - 1 }}–Mai/{{ year }}</option>
          <option :value="`${year}-S2`">S2 {{ year }} · Jun–Nov/{{ year }}</option>
        </template>
      </template>
    </select>
  </label>
</template>
