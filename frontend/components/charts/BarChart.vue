<script setup lang="ts">
interface BarPoint {
  label: string;
  value: number | null;
}

const props = withDefaults(
  defineProps<{
    points: BarPoint[];
    target?: number | null;
    suffix?: string;
    color?: string;
    seriesLabel?: string;
    showLegend?: boolean;
    showValues?: boolean;
  }>(),
  {
    target: null,
    suffix: "",
    color: "#304f7e",
    seriesLabel: "Resultado",
    showLegend: true,
    showValues: true,
  },
);

const hoveredIndex = ref<number | null>(null);

const width = 760;
const height = 300;

const pad = {
  left: 56,
  right: 26,
  top: 30,
  bottom: 58,
};

const plotWidth = width - pad.left - pad.right;
const plotHeight = height - pad.top - pad.bottom;

const validValues = computed(() =>
  props.points
    .map((point) => point.value)
    .filter(
      (value): value is number =>
        typeof value === "number" && Number.isFinite(value),
    ),
);

const max = computed(() => {
  const rawMax = Math.max(1, ...validValues.value, props.target ?? 0);

  if (props.suffix === "%" && rawMax <= 100) {
    return 100;
  }

  return Math.ceil(rawMax * 1.12);
});

const slot = computed(
  () => plotWidth / Math.max(1, props.points.length),
);

const barWidth = computed(() =>
  Math.min(62, Math.max(18, slot.value * 0.56)),
);

const x = (index: number) =>
  pad.left + index * slot.value + slot.value / 2;

const barX = (index: number) => x(index) - barWidth.value / 2;

const y = (value: number) =>
  height - pad.bottom - (value / max.value) * plotHeight;

const barHeight = (value: number) =>
  Math.max(0, height - pad.bottom - y(value));

const yTicks = computed(() => {
  const steps = 4;

  return Array.from({ length: steps + 1 }, (_, index) => {
    const value = (max.value / steps) * index;

    return {
      value,
      y: y(value),
    };
  }).reverse();
});

const targetY = computed(() => {
  if (props.target === null) {
    return null;
  }

  return y(props.target);
});

interface HoveredBarPoint {
  label: string;
  value: number;
  index: number;
}

const hoveredPoint = computed<HoveredBarPoint | null>(() => {
  const index = hoveredIndex.value;

  if (index === null) {
    return null;
  }

  const point = props.points[index];
  const value = point?.value;

  if (
    !point ||
    typeof value !== "number" ||
    !Number.isFinite(value)
  ) {
    return null;
  }

  return {
    label: point.label,
    value,
    index,
  };
});

const tooltipStyle = computed(() => {
  if (!hoveredPoint.value) {
    return {};
  }

  const px = (x(hoveredPoint.value.index) / width) * 100;
  const py = (y(hoveredPoint.value.value) / height) * 100;
  const alignRight = px > 62;

  return {
    left: `${px}%`,
    top: `${py}%`,
    transform: `translate(${alignRight ? "-100%" : "0%"}, -100%) translate(${alignRight ? "-10px" : "10px"}, -10px)`,
  };
});

const showInlineValues = computed(
  () => props.showValues && props.points.length <= 10,
);

const legendText = computed(() =>
  props.suffix
    ? `${props.seriesLabel} (${props.suffix})`
    : props.seriesLabel,
);

const ariaLabel = computed(() =>
  props.points
    .map((point) =>
      point.value === null
        ? `${point.label}: sem dados`
        : `${point.label}: ${formatValue(point.value)}${props.suffix}`,
    )
    .join(", "),
);

function formatValue(value: number) {
  return new Intl.NumberFormat("pt-BR", {
    maximumFractionDigits: 2,
  }).format(value);
}

function shortLabel(label: string) {
  return label.length > 12
    ? `${label.slice(0, 11)}…`
    : label;
}

function valueLabelIsInside(value: number) {
  return y(value) <= pad.top + 22;
}

function activate(index: number) {
  hoveredIndex.value = index;
}

function deactivate(index: number) {
  if (hoveredIndex.value === index) {
    hoveredIndex.value = null;
  }
}
</script>

<template>
  <div class="bar-chart">
    <div class="chart-stage">
      <svg
        class="chart-svg"
        :viewBox="`0 0 ${width} ${height}`"
        role="img"
        :aria-label="ariaLabel"
        preserveAspectRatio="xMidYMid meet"
      >
        <!-- Grade horizontal -->
        <g v-for="tick in yTicks" :key="tick.value">
          <line
            :x1="pad.left"
            :x2="width - pad.right"
            :y1="tick.y"
            :y2="tick.y"
            class="chart-grid-line"
          />

          <text
            :x="pad.left - 9"
            :y="tick.y + 4"
            text-anchor="end"
            class="chart-axis-label"
          >
            {{ formatValue(tick.value) }}{{ suffix }}
          </text>
        </g>

        <!-- Eixos -->
        <line
          :x1="pad.left"
          :x2="pad.left"
          :y1="pad.top"
          :y2="height - pad.bottom"
          class="chart-axis"
        />

        <line
          :x1="pad.left"
          :x2="width - pad.right"
          :y1="height - pad.bottom"
          :y2="height - pad.bottom"
          class="chart-axis"
        />

        <!-- Meta -->
        <template v-if="target !== null && targetY !== null">
          <line
            :x1="pad.left"
            :x2="width - pad.right"
            :y1="targetY"
            :y2="targetY"
            class="chart-target"
          />

          <text
            :x="width - pad.right - 2"
            :y="targetY - 8"
            text-anchor="end"
            class="chart-target-label"
          >
            Meta {{ formatValue(target) }}{{ suffix }}
          </text>
        </template>

        <!-- Destaque vertical ao passar o mouse -->
        <rect
          v-if="hoveredPoint"
          :x="pad.left + hoveredPoint.index * slot"
          :y="pad.top"
          :width="slot"
          :height="plotHeight"
          class="chart-hover-band"
        />

        <template
          v-for="(point, index) in points"
          :key="`${point.label}-${index}`"
        >
          <template v-if="point.value !== null && Number.isFinite(point.value)">
            <!-- Trilho de fundo deixa as barras mais integradas ao dashboard -->
            <rect
              :x="barX(index)"
              :y="pad.top"
              :width="barWidth"
              :height="plotHeight"
              rx="7"
              class="chart-bar-track"
              :class="{ 'chart-bar-track--active': hoveredIndex === index }"
            />

            <!-- Barra -->
            <rect
              :x="barX(index)"
              :y="y(point.value)"
              :width="barWidth"
              :height="barHeight(point.value)"
              rx="7"
              :fill="color"
              class="chart-bar"
              :class="{
                'chart-bar--active': hoveredIndex === index,
                'chart-bar--muted':
                  hoveredIndex !== null && hoveredIndex !== index,
              }"
              role="graphics-symbol"
              :aria-label="`${point.label}: ${formatValue(point.value)}${suffix}`"
              tabindex="0"
              @mouseenter="activate(index)"
              @mouseleave="deactivate(index)"
              @focus="activate(index)"
              @blur="deactivate(index)"
            >
              <title>
                {{ point.label }}: {{ formatValue(point.value) }}{{ suffix }}
              </title>
            </rect>

            <!-- Valor sobre a barra -->
            <text
              v-if="showInlineValues || hoveredIndex === index"
              :x="x(index)"
              :y="Math.max(pad.top + 12, y(point.value) - 8)"
              text-anchor="middle"
              class="chart-value-label"
              :class="{
                'chart-value-label--inside': valueLabelIsInside(point.value),
                'chart-value-label--active': hoveredIndex === index,
              }"
            >
              {{ formatValue(point.value) }}{{ suffix }}
            </text>

            <!-- Área de hover ampliada -->
            <rect
              :x="pad.left + index * slot"
              :y="pad.top"
              :width="slot"
              :height="plotHeight + 38"
              fill="transparent"
              class="chart-hit-area"
              @mouseenter="activate(index)"
              @mouseleave="deactivate(index)"
            />
          </template>

          <!-- Rótulo X -->
          <text
            :x="x(index)"
            :y="height - 29"
            text-anchor="middle"
            class="chart-x-label"
            :class="{ 'chart-x-label--active': hoveredIndex === index }"
          >
            {{ shortLabel(point.label) }}
          </text>
        </template>
      </svg>

      <!-- Tooltip no mesmo padrão do LineChart -->
      <div
        v-if="hoveredPoint"
        class="chart-tooltip"
        :style="tooltipStyle"
      >
        <div class="chart-tooltip-title">
          {{ hoveredPoint.label }}
        </div>

        <div class="chart-tooltip-row">
          <span
            class="chart-tooltip-dot"
            :style="{ backgroundColor: color }"
          />
          <span>
            {{ seriesLabel }}:
            <strong>
              {{ formatValue(hoveredPoint.value) }}{{ suffix }}
            </strong>
          </span>
        </div>

        <div v-if="target !== null" class="chart-tooltip-row">
          <span
            class="chart-tooltip-dot"
            style="background-color: #eaa239"
          />
          <span>
            Meta:
            <strong>{{ formatValue(target) }}{{ suffix }}</strong>
          </span>
        </div>
      </div>
    </div>

    <!-- Legenda -->
    <div v-if="showLegend" class="chart-legend">
      <span class="chart-legend-item">
        <span
          class="chart-legend-square"
          :style="{ backgroundColor: color }"
        />
        <span>{{ legendText }}</span>
      </span>

      <span v-if="target !== null" class="chart-legend-item">
        <span class="chart-legend-target" />
        <span>Meta {{ formatValue(target) }}{{ suffix }}</span>
      </span>
    </div>
  </div>
</template>

<style scoped>
.bar-chart {
  width: 100%;
  min-height: 310px;

  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: center;
}

.chart-stage {
  position: relative;

  width: 100%;
}

.chart-svg {
  display: block;

  width: 100%;
  height: auto;

  overflow: visible;
}

/* Grade e eixos no mesmo padrão visual do LineChart */
.chart-grid-line {
  stroke: #edf1f5;
  stroke-width: 1;
}

.chart-axis {
  stroke: #9aa3ad;
  stroke-width: 1.15;
}

.chart-axis-label,
.chart-x-label {
  fill: #7f8996;

  font-size: 10px;
  font-weight: 400;

  transition:
    fill 0.15s ease,
    font-weight 0.15s ease;
}

.chart-x-label--active {
  fill: #1f2937;
  font-weight: 700;
}

/* Meta */
.chart-target {
  stroke: #eaa239;
  stroke-width: 1.4;
  stroke-dasharray: 7 6;

  pointer-events: none;
}

.chart-target-label {
  fill: #aa721e;

  font-size: 10px;
  font-weight: 600;

  pointer-events: none;
}

/* Faixa vertical suave para evidenciar a categoria em hover */
.chart-hover-band {
  fill: #f7f9fc;

  pointer-events: none;
}

/* Trilho de cada barra */
.chart-bar-track {
  fill: #f3f5f8;

  transition:
    fill 0.15s ease,
    opacity 0.15s ease;
}

.chart-bar-track--active {
  fill: #edf1f6;
}

/* Barra principal */
.chart-bar {
  cursor: pointer;

  opacity: 0.94;

  outline: none;

  transform-box: fill-box;
  transform-origin: center bottom;

  transition:
    opacity 0.16s ease,
    filter 0.16s ease,
    transform 0.16s ease;
}

.chart-bar--active {
  opacity: 1;

  filter: drop-shadow(0 5px 7px rgba(15, 23, 42, 0.14));

  transform: scaleX(1.045);
}

.chart-bar--muted {
  opacity: 0.38;
}

.chart-bar:focus-visible {
  stroke: #1f2937;
  stroke-width: 2;
}

/* Valor sobre as barras */
.chart-value-label {
  fill: #334155;

  font-size: 9px;
  font-weight: 600;

  pointer-events: none;

  transition:
    fill 0.15s ease,
    font-weight 0.15s ease;
}

.chart-value-label--inside {
  fill: #ffffff;
  font-weight: 700;
  paint-order: stroke;
  stroke: rgba(30, 55, 95, 0.35);
  stroke-width: 1.5px;
  stroke-linejoin: round;
}

.chart-value-label--active {
  fill: #334155;
  font-weight: 800;
}

.chart-value-label--inside.chart-value-label--active {
  fill: #ffffff;
  stroke: rgba(30, 55, 95, 0.45);
}

.chart-hit-area {
  cursor: pointer;
}

/* Tooltip compartilhando a linguagem visual do LineChart */
.chart-tooltip {
  position: absolute;
  z-index: 5;

  min-width: 160px;

  padding: 9px 12px;

  background: #f3f4f6;
  border: 1px solid #d8dde3;
  border-radius: 8px;
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.12);

  color: #1f2937;

  font-size: 12px;

  pointer-events: none;
}

.chart-tooltip-title {
  margin-bottom: 6px;

  color: #344054;

  font-weight: 700;
}

.chart-tooltip-row {
  display: flex;
  align-items: center;

  gap: 6px;

  padding: 2px 0;
}

.chart-tooltip-dot {
  width: 8px;
  height: 8px;

  flex-shrink: 0;

  border-radius: 50%;
}

/* Legenda inferior */
.chart-legend {
  min-height: 30px;

  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;

  gap: 8px 18px;

  color: #62708a;

  font-size: 12px;
}

.chart-legend-item {
  display: inline-flex;
  align-items: center;

  gap: 7px;
}

.chart-legend-square {
  width: 9px;
  height: 9px;

  border-radius: 3px;
}

.chart-legend-target {
  width: 20px;
  height: 0;

  border-top: 2px dashed #eaa239;
}

/* Responsividade */
@media (max-width: 768px) {
  .bar-chart {
    min-height: 275px;
  }

  .chart-axis-label,
  .chart-x-label {
    font-size: 9px;
  }

  .chart-value-label {
    font-size: 8.5px;
  }

  .chart-tooltip {
    min-width: 145px;

    padding: 8px 10px;

    font-size: 11px;
  }

  .chart-legend {
    font-size: 11px;
  }
}
</style>
