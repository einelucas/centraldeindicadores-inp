<script setup lang="ts">
const props = withDefaults(defineProps<{
  points: Array<{ label: string; value: number | null }>;
  target?: number | null;
  suffix?: string;
  color?: string;
}>(), { target: null, suffix: "", color: "#304f7e" });

const width = 720;
const height = 270;
const pad = { left: 48, right: 22, top: 22, bottom: 48 };
const valid = computed(() => props.points.map((item) => item.value).filter((value): value is number => typeof value === "number"));
const max = computed(() => Math.max(1, ...valid.value, props.target ?? 0) * 1.12);
const x = (index: number) => pad.left + (index * (width - pad.left - pad.right)) / Math.max(1, props.points.length - 1);
const y = (value: number) => height - pad.bottom - (value / max.value) * (height - pad.top - pad.bottom);
const line = computed(() => props.points.map((item, index) => item.value === null ? null : `${x(index)},${y(item.value)}`).filter(Boolean).join(" "));
</script>

<template>
  <svg class="chart-svg" :viewBox="`0 0 ${width} ${height}`" role="img" aria-label="Gráfico de evolução">
    <line :x1="pad.left" :y1="height - pad.bottom" :x2="width - pad.right" :y2="height - pad.bottom" stroke="#dfe5ed" />
    <line v-if="target !== null" :x1="pad.left" :x2="width-pad.right" :y1="y(target)" :y2="y(target)" stroke="#eaa239" stroke-dasharray="6 5" />
    <text v-if="target !== null" :x="width-pad.right" :y="y(target)-6" text-anchor="end" fill="#a76b17" font-size="10">Meta {{ target }}{{ suffix }}</text>
    <polyline v-if="line" :points="line" fill="none" :stroke="color" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
    <template v-for="(point, index) in points" :key="`${point.label}-${index}`">
      <circle v-if="point.value !== null" :cx="x(index)" :cy="y(point.value)" r="4" :fill="color"><title>{{ point.label }}: {{ point.value }}{{ suffix }}</title></circle>
      <text :x="x(index)" :y="height-24" text-anchor="middle" fill="#718096" font-size="10">{{ point.label }}</text>
      <text v-if="point.value !== null" :x="x(index)" :y="y(point.value)-9" text-anchor="middle" fill="#34445a" font-size="10" font-weight="700">{{ point.value }}{{ suffix }}</text>
    </template>
  </svg>
</template>
