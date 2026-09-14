<script setup lang="ts">
import { formatNumber } from "~/utils/format";

interface LinePoint {
  label: string;
  value: number | null;
}

const props = withDefaults(
  defineProps<{
    points: LinePoint[];
    target?: number | null;
    suffix?: string;
    color?: string;
    seriesLabel?: string;
    showLegend?: boolean;
  }>(),
  {
    target: null,
    suffix: "",
    color: "#304f7e",
    seriesLabel: "Resultado",
    showLegend: true,
  },
);

const hoveredIndex = ref<number | null>(null);
const formatValue = (value: number) => formatNumber(value, props.suffix === "%" ? 1 : 2);

/*
 * Dimensões internas.
 * O SVG é responsivo; estes valores definem apenas
 * o sistema de coordenadas.
 */
const width = 760;
const height = 300;

const pad = {
  left: 56,
  right: 26,
  top: 26,
  bottom: 54,
};

const plotWidth = width - pad.left - pad.right;
const plotHeight = height - pad.top - pad.bottom;

const valid = computed(() =>
  props.points
    .map((item) => item.value)
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value)),
);

/*
 * Em gráficos percentuais mantém 0–100,
 * como no painel de referência.
 */
const max = computed(() => {
  const rawMax = Math.max(1, ...valid.value, props.target ?? 0);

  if (props.suffix === "%" && rawMax <= 100) {
    return 100;
  }

  return Math.ceil(rawMax * 1.1);
});

const x = (index: number) => {
  if (props.points.length <= 1) {
    return pad.left + plotWidth / 2;
  }

  return pad.left + (index * plotWidth) / (props.points.length - 1);
};

const y = (value: number) => height - pad.bottom - (value / max.value) * plotHeight;

/*
 * Apenas pontos válidos entram na linha.
 */
const chartPoints = computed(() =>
  props.points
    .map((point, index) => ({
      ...point,
      index,
      x: x(index),
      y: point.value !== null ? y(point.value) : null,
    }))
    .filter(
      (
        point,
      ): point is {
        label: string;
        value: number;
        index: number;
        x: number;
        y: number;
      } => point.value !== null && point.y !== null && Number.isFinite(point.value),
    ),
);

/*
 * Converte os pontos em curvas Bézier.
 *
 * Em vez de <polyline>, usamos <path> com
 * curvas cúbicas para criar o visual suave
 * da referência.
 */
function buildSmoothPath(
  points: Array<{
    x: number;
    y: number;
  }>,
) {
  if (!points.length) {
    return "";
  }

  const first = points[0];

  if (!first) {
    return "";
  }

  if (points.length === 1) {
    return `M ${first.x} ${first.y}`;
  }

  const second = points[1];

  if (points.length === 2 && second) {
    return [`M ${first.x} ${first.y}`, `L ${second.x} ${second.y}`].join(" ");
  }

  /*
   * Quanto maior, mais acentuada a curva.
   * 0.16–0.20 funciona bem para dashboards.
   */
  const tension = 0.18;

  let path = `M ${first.x} ${first.y}`;

  for (let index = 0; index < points.length - 1; index++) {
    const current = points[index];

    const next = points[index + 1];

    if (!current || !next) {
      continue;
    }

    const previous = points[index - 1] ?? current;

    const afterNext = points[index + 2] ?? next;

    const cp1x = current.x + (next.x - previous.x) * tension;

    const cp1y = current.y + (next.y - previous.y) * tension;

    const cp2x = next.x - (afterNext.x - current.x) * tension;

    const cp2y = next.y - (afterNext.y - current.y) * tension;

    path += ` C ${cp1x} ${cp1y},` + ` ${cp2x} ${cp2y},` + ` ${next.x} ${next.y}`;
  }

  return path;
}

const linePath = computed(() => buildSmoothPath(chartPoints.value));

/*
 * 0 / 25 / 50 / 75 / 100
 */
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

const legendText = computed(() =>
  props.suffix ? `${props.seriesLabel} (${props.suffix})` : props.seriesLabel,
);

const hoveredPoint = computed(() => {
  if (hoveredIndex.value === null) {
    return null;
  }

  const point = props.points[hoveredIndex.value];
  const value = point?.value;

  if (!point || value === null || value === undefined) {
    return null;
  }

  return { label: point.label, value, index: hoveredIndex.value };
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
</script>

<template>
  <div class="line-chart">
    <svg
      class="chart-svg"
      :viewBox="`0 0 ${width} ${height}`"
      role="img"
      aria-label="Gráfico de evolução"
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

        <text :x="pad.left - 9" :y="tick.y + 4" text-anchor="end" class="chart-axis-label">
          {{ Math.round(tick.value) }}{{ suffix }}
        </text>
      </g>

      <!-- Eixo Y -->
      <line
        :x1="pad.left"
        :x2="pad.left"
        :y1="pad.top"
        :y2="height - pad.bottom"
        class="chart-axis"
      />

      <!-- Eixo X -->
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

      <!-- Guia vertical do hover -->
      <line
        v-if="hoveredPoint"
        :x1="x(hoveredPoint.index)"
        :x2="x(hoveredPoint.index)"
        :y1="pad.top"
        :y2="height - pad.bottom"
        class="chart-hover-guide"
      />

      <!-- Linha suave -->
      <path v-if="linePath" :d="linePath" fill="none" :stroke="color" class="chart-line" />

      <!-- Pontos -->
      <template v-for="(point, index) in points" :key="`${point.label}-${index}`">
        <template v-if="point.value !== null">
          <!-- Halo no hover -->
          <circle
            v-if="hoveredIndex === index"
            :cx="x(index)"
            :cy="y(point.value)"
            r="10"
            :fill="color"
            opacity="0.12"
          />

          <circle
            class="chart-point"
            :cx="x(index)"
            :cy="y(point.value)"
            :fill="color"
            :r="hoveredIndex === index ? 7 : 6"
            @mouseenter="hoveredIndex = index"
            @mouseleave="hoveredIndex = null"
          >
            <title>{{ point.label }}: {{ formatValue(point.value) }}{{ suffix }}</title>
          </circle>
        </template>

        <!-- Rótulo do eixo X -->
        <text
          :x="x(index)"
          :y="height - 29"
          text-anchor="middle"
          class="chart-x-label"
          :class="{ 'chart-x-label--active': hoveredIndex === index }"
        >
          {{ point.label }}
        </text>

        <!-- Área de hover ampliada -->
        <rect
          v-if="point.value !== null"
          :x="x(index) - plotWidth / Math.max(1, points.length * 2)"
          y="0"
          :width="plotWidth / Math.max(1, points.length)"
          :height="height"
          fill="transparent"
          @mouseenter="hoveredIndex = index"
          @mouseleave="hoveredIndex = null"
        />
      </template>
    </svg>

    <!-- Tooltip customizada -->
    <div v-if="hoveredPoint" class="chart-tooltip" :style="tooltipStyle">
      <div class="chart-tooltip-title">{{ hoveredPoint.label }}</div>
      <div class="chart-tooltip-row">
        <span class="chart-tooltip-dot" :style="{ backgroundColor: color }" />
        <span>{{ seriesLabel }}: <strong>{{ formatValue(hoveredPoint.value) }}{{ suffix }}</strong></span>
      </div>
      <div v-if="target !== null" class="chart-tooltip-row">
        <span class="chart-tooltip-dot" style="background-color: #eaa239" />
        <span>Meta: <strong>{{ formatValue(target) }}{{ suffix }}</strong></span>
      </div>
    </div>

    <!-- Legenda -->
    <div v-if="showLegend" class="chart-legend">
      <span class="chart-legend-symbol">
        <span
          class="chart-legend-line"
          :style="{
            backgroundColor: color,
          }"
        />

        <span
          class="chart-legend-dot"
          :style="{
            backgroundColor: color,
          }"
        />
      </span>

      <span>
        {{ legendText }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.line-chart {
  position: relative;

  width: 100%;
  min-height: 300px;

  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: center;
}

.chart-hover-guide {
  stroke: #c3cbd6;
  stroke-width: 1;
  stroke-dasharray: 4 4;
  pointer-events: none;
}

.chart-x-label--active {
  fill: #1f2937;
  font-weight: 600;
}

.chart-tooltip {
  position: absolute;
  z-index: 5;

  min-width: 150px;

  padding: 8px 12px;

  background: #f3f4f6;
  border: 1px solid #d8dde3;
  border-radius: 8px;
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.12);

  font-size: 12px;
  color: #1f2937;

  pointer-events: none;
}

.chart-tooltip-title {
  margin-bottom: 6px;

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

  border-radius: 50%;

  flex-shrink: 0;
}

.chart-svg {
  display: block;

  width: 100%;
  height: auto;

  overflow: visible;
}

/* Grade mais leve */
.chart-grid-line {
  stroke: #edf1f5;
  stroke-width: 1;
}

/* Eixos */
.chart-axis {
  stroke: #9aa3ad;
  stroke-width: 1.15;
}

/* Textos dos eixos */
.chart-axis-label,
.chart-x-label {
  fill: #7f8996;
  font-size: 10px;
  font-weight: 400;
}

/* Linha principal */
.chart-line {
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}

/* Pontos */
.chart-point {
  cursor: pointer;

  stroke: #ffffff;
  stroke-width: 1.5;

  transition:
    r 0.15s ease,
    opacity 0.15s ease;
}

/* Meta */
.chart-target {
  stroke: #eaa239;
  stroke-width: 1.4;
  stroke-dasharray: 7 6;
}

.chart-target-label {
  fill: #aa721e;
  font-size: 10px;
  font-weight: 500;
}

/* Legenda */
.chart-legend {
  min-height: 28px;

  display: flex;
  align-items: center;
  justify-content: center;

  gap: 7px;

  color: #62708a;

  font-size: 12px;
}

.chart-legend-symbol {
  position: relative;

  width: 18px;
  height: 10px;

  display: inline-flex;
  align-items: center;
}

.chart-legend-line {
  position: absolute;
  left: 0;
  right: 0;

  height: 2px;

  border-radius: 999px;
}

.chart-legend-dot {
  position: absolute;

  left: 50%;
  top: 50%;

  width: 6px;
  height: 6px;

  border: 1px solid #ffffff;
  border-radius: 50%;

  transform: translate(-50%, -50%);
}

@media (max-width: 768px) {
  .line-chart {
    min-height: 260px;
  }

  .chart-axis-label,
  .chart-x-label,
  .chart-target-label {
    font-size: 9px;
  }

  .chart-legend {
    font-size: 11px;
  }
}
</style>
