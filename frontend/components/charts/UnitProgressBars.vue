<script setup lang="ts">
import { formatNumber } from "~/utils/format";

interface ProgressItem {
  label: string;
  value: number;
  sublabel?: string;
}

const props = withDefaults(
  defineProps<{
    items: ProgressItem[];
    target?: number | null;
    suffix?: string;
    okColor?: string;
    badColor?: string;
    emptyMessage?: string;
  }>(),
  {
    target: null,
    suffix: "%",
    okColor: "#609346",
    badColor: "#cc5121",
    emptyMessage: "Sem unidades publicadas.",
  },
);

const hoveredLabel = ref<string | null>(null);
const formatValue = (value: number) => formatNumber(value, props.suffix === "%" ? 1 : 2);

const isOk = (value: number) => props.target === null || value >= props.target;
const colorFor = (value: number) => (isOk(value) ? props.okColor : props.badColor);
const widthFor = (value: number) => `${Math.min(100, Math.max(0, value))}%`;
</script>

<template>
  <div class="unit-progress-bars">
    <template v-if="items.length">
      <div
        v-for="item in items"
        :key="item.label"
        class="urow"
        :class="{ 'urow--hovered': hoveredLabel === item.label }"
        @mouseenter="hoveredLabel = item.label"
        @mouseleave="hoveredLabel = null"
      >
        <div class="uname">
          {{ item.label }}
          <span v-if="item.sublabel" class="uname-sub">{{ item.sublabel }}</span>
        </div>

        <div class="utrack">
          <div
            class="ufill"
            :style="{
              width: widthFor(item.value),
              background: colorFor(item.value),
            }"
          />
        </div>

        <div class="uval" :style="{ color: colorFor(item.value) }">
          {{ formatValue(item.value) }}{{ suffix }}
        </div>
      </div>
    </template>

    <p v-else class="ps">{{ emptyMessage }}</p>
  </div>
</template>

<style scoped>
.urow--hovered .ufill {
  filter: brightness(1.08);
}

.urow--hovered .uname {
  font-weight: 700;
}
</style>
