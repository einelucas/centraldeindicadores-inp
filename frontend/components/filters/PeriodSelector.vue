<script setup lang="ts">
import type { AvailablePeriod, PeriodRange } from "~/types/api";
import { INDICATOR_DATA_CHANGED_EVENT } from "~/utils/browser-events";
import { periodFromAvailable } from "~/utils/period";

const model = defineModel<PeriodRange>({ required: true });
const props = withDefaults(defineProps<{ allowAll?: boolean }>(), { allowAll: false });
const api = useApi();
const periods = ref<AvailablePeriod[]>([]);
const selected = ref("");
const loading = ref(true);
const loadError = ref(false);

function same(a: PeriodRange, b: PeriodRange) {
  return a.startYear === b.startYear && a.startMonth === b.startMonth && a.endYear === b.endYear && a.endMonth === b.endMonth;
}

function syncSelection() {
  if (loading.value) return;

  const found = periods.value.find((item) => same(periodFromAvailable(item), model.value));
  if (found) {
    selected.value = found.periodKey;
    return;
  }

  if (props.allowAll) {
    selected.value = "all";
    return;
  }

  const mostRecent = periods.value[0];
  selected.value = mostRecent?.periodKey ?? "";
  if (mostRecent) model.value = periodFromAvailable(mostRecent);
}

function update() {
  if (selected.value === "all" && props.allowAll) return;
  const found = periods.value.find((item) => item.periodKey === selected.value);
  if (found) model.value = periodFromAvailable(found);
}

async function loadPeriods() {
  loading.value = true;
  loadError.value = false;
  selected.value = "";

  try {
    const response = await api.get<{ periods: AvailablePeriod[] }>("/available-periods");
    periods.value = Array.isArray(response.periods) ? response.periods : [];
  } catch {
    periods.value = [];
    loadError.value = true;
  } finally {
    loading.value = false;
    syncSelection();
  }
}

onMounted(() => {
  void loadPeriods();
  window.addEventListener(INDICATOR_DATA_CHANGED_EVENT, loadPeriods);
});

onBeforeUnmount(() => {
  window.removeEventListener(INDICATOR_DATA_CHANGED_EVENT, loadPeriods);
});

watch(model, syncSelection, { deep: true });
</script>

<template>
  <label class="field">
    <span>Período operacional</span>
    <select
      v-model="selected"
      :disabled="loading || (!allowAll && !periods.length)"
      :aria-busy="loading"
      @change="update"
    >
      <option v-if="loading" disabled value="">Carregando períodos…</option>
      <template v-else>
        <option v-if="loadError" disabled value="">Não foi possível carregar os períodos</option>
        <option v-else-if="!periods.length && !allowAll" disabled value="">Nenhum período disponível</option>
        <option v-if="allowAll" value="all">Todos</option>
        <option v-for="item in periods" :key="item.periodKey" :value="item.periodKey">{{ item.label }}</option>
      </template>
    </select>
  </label>
</template>
