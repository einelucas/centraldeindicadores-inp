<script setup lang="ts">
const props = withDefaults(defineProps<{
  points: Array<{ label: string; value: number | null }>;
  target?: number | null;
  suffix?: string;
  color?: string;
}>(), { target: null, suffix: "", color: "#007cc5" });

const width = 720, height = 270, left = 45, right = 20, top = 24, bottom = 62;
const max = computed(() => {
  const rawMax = Math.max(1, ...props.points.map(p => p.value ?? 0), props.target ?? 0);
  if (props.suffix === "%" && rawMax <= 100) return 100;
  return rawMax * 1.12;
});
const slot = computed(() => (width-left-right) / Math.max(1, props.points.length));
const y = (value: number) => height-bottom-(value/max.value)*(height-top-bottom);
const yTicks = computed(() => {
  const steps = 4;
  return Array.from({ length: steps + 1 }, (_, i) => {
    const value = (max.value / steps) * i;
    return { value, y: y(value) };
  });
});
</script>

<template>
  <svg class="chart-svg bar-chart" :viewBox="`0 0 ${width} ${height}`" role="img" aria-label="Gráfico de barras">
    <g v-for="tick in yTicks" :key="tick.value">
      <line :x1="left" :x2="width - right" :y1="tick.y" :y2="tick.y" stroke="#f0f2f5" />
      <text :x="left - 8" :y="tick.y + 3" text-anchor="end" fill="#a6afbb" font-size="9">{{ Math.round(tick.value) }}{{ suffix }}</text>
    </g>
    <line :x1="left" :y1="height-bottom" :x2="width-right" :y2="height-bottom" stroke="#dfe5ed" />
    <line v-if="target !== null" :x1="left" :x2="width-right" :y1="y(target)" :y2="y(target)" stroke="#eaa239" stroke-dasharray="6 5" />
    <template v-for="(point,index) in points" :key="`${point.label}-${index}`">
      <rect v-if="point.value !== null" class="chart-bar" :x="left+index*slot+slot*.18" :y="y(point.value)" :width="slot*.64" :height="height-bottom-y(point.value)" rx="5" :fill="color"><title>{{ point.label }}: {{ point.value }}{{ suffix }}</title></rect>
      <text :x="left+index*slot+slot/2" :y="height-38" text-anchor="middle" fill="#718096" font-size="10">{{ point.label.length > 12 ? point.label.slice(0, 11)+'…' : point.label }}</text>
    </template>
  </svg>
</template>

<style scoped>
.bar-chart { min-height: 280px; }
.chart-bar { cursor: pointer; transition: opacity 0.15s ease; }
.chart-bar:hover { opacity: 0.8; }

@media (max-width: 768px) {
  .bar-chart { min-height: 275px; }
}
</style>
