<script setup lang="ts">
const props = withDefaults(defineProps<{
  points: Array<{ label: string; value: number | null }>;
  target?: number | null;
  suffix?: string;
  color?: string;
}>(), { target: null, suffix: "", color: "#007cc5" });

const width = 720, height = 270, left = 45, right = 20, top = 24, bottom = 62;
const max = computed(() => Math.max(1, ...props.points.map(p => p.value ?? 0), props.target ?? 0) * 1.12);
const slot = computed(() => (width-left-right) / Math.max(1, props.points.length));
const y = (value: number) => height-bottom-(value/max.value)*(height-top-bottom);
</script>

<template>
  <svg class="chart-svg" :viewBox="`0 0 ${width} ${height}`" role="img" aria-label="Gráfico de barras">
    <line :x1="left" :y1="height-bottom" :x2="width-right" :y2="height-bottom" stroke="#dfe5ed" />
    <line v-if="target !== null" :x1="left" :x2="width-right" :y1="y(target)" :y2="y(target)" stroke="#eaa239" stroke-dasharray="6 5" />
    <template v-for="(point,index) in points" :key="`${point.label}-${index}`">
      <rect v-if="point.value !== null" :x="left+index*slot+slot*.18" :y="y(point.value)" :width="slot*.64" :height="height-bottom-y(point.value)" rx="5" :fill="color"><title>{{ point.label }}: {{ point.value }}{{ suffix }}</title></rect>
      <text :x="left+index*slot+slot/2" :y="height-38" text-anchor="middle" fill="#718096" font-size="10">{{ point.label.length > 12 ? point.label.slice(0, 11)+'…' : point.label }}</text>
      <text v-if="point.value !== null" :x="left+index*slot+slot/2" :y="y(point.value)-7" text-anchor="middle" fill="#34445a" font-size="10" font-weight="700">{{ point.value }}{{ suffix }}</text>
    </template>
  </svg>
</template>
