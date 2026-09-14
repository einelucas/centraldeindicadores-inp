<script setup lang="ts">
import { formatNumber } from "~/utils/format";

interface DonutItem {
  label: string;
  value: number;
  color: string;
}

const props = withDefaults(
  defineProps<{
    items: DonutItem[];
    suffix?: string;
    showValues?: boolean;
    showLegendValues?: boolean;
  }>(),
  {
    suffix: "%",
    showValues: true,
    showLegendValues: false,
  },
);

const hovered = ref<string | null>(null);
const formatValue = (value: number) => formatNumber(value, props.suffix === "%" ? 1 : 2);

const safeItems = computed(() =>
  props.items.map((item) => ({
    ...item,
    value: Number.isFinite(item.value) && item.value > 0 ? item.value : 0,
  })),
);

const total = computed(() => safeItems.value.reduce((sum, item) => sum + item.value, 0));

const segments = computed(() => {
  if (total.value <= 0) {
    return [];
  }

  let offset = 0;

  return safeItems.value.map((item) => {
    const share = (item.value / total.value) * 100;

    const middle = offset + share / 2;

    /*
     * -90 graus faz o gráfico começar pelo topo.
     */
    const angle = -90 + middle * 3.6;
    const radians = (angle * Math.PI) / 180;

    /*
     * Compensa a largura do texto projetada na direção radial. Assim, a borda
     * mais próxima de cada percentual mantém praticamente o mesmo afastamento
     * do anel, inclusive nas laterais, onde os rótulos são mais largos.
     */
    const labelText = `${formatValue(item.value)}${props.suffix}`;
    const outerRadius = 47;
    const labelGap = 5;
    const halfTextWidth = labelText.length * 2.2;
    const halfTextHeight = 4;
    const projectedHalfSize = Math.abs(Math.cos(radians)) * halfTextWidth
      + Math.abs(Math.sin(radians)) * halfTextHeight;
    const labelRadius = outerRadius + labelGap + projectedHalfSize;

    const labelX = 60 + Math.cos(radians) * labelRadius;
    const labelY = 60 + Math.sin(radians) * labelRadius;

    /*
     * Pequeno espaço branco entre os segmentos.
     */
    const gap = Math.min(0.7, share * 0.2);

    const segment = {
      ...item,
      share,
      offset,
      visibleShare: Math.max(share - gap, 0),
      labelText,
      labelX,
      labelY,
    };

    offset += share;

    return segment;
  });
});

const ariaLabel = computed(() =>
  props.items.map((item) => `${item.label}: ${formatValue(item.value)}${props.suffix}`).join(", "),
);
</script>

<template>
  <div class="donut-chart">
    <div class="donut-visual">
      <svg viewBox="0 0 120 120" role="img" :aria-label="ariaLabel">
        <!-- Fundo do donut -->
        <circle cx="60" cy="60" r="39" fill="none" stroke="#f0f2f5" stroke-width="16" />

        <!-- Segmentos -->
        <circle
          v-for="segment in segments"
          :key="segment.label"
          cx="60"
          cy="60"
          r="39"
          fill="none"
          :stroke="segment.color"
          stroke-width="16"
          pathLength="100"
          :stroke-dasharray="`${segment.visibleShare} ${100 - segment.visibleShare}`"
          :stroke-dashoffset="-segment.offset"
          transform="rotate(-90 60 60)"
          stroke-linecap="butt"
          :opacity="hovered && hovered !== segment.label ? 0.35 : 1"
          class="donut-segment"
          @mouseenter="hovered = segment.label"
          @mouseleave="hovered = null"
        >
          <title>{{ segment.label }}: {{ formatValue(segment.value) }}{{ suffix }}</title>
        </circle>

        <!-- Valores posicionados ao redor do donut -->
        <template v-if="showValues">
          <text
            v-for="segment in segments"
            :key="`label-${segment.label}`"
            :x="segment.labelX"
            :y="segment.labelY"
            :fill="segment.color"
            text-anchor="middle"
            dominant-baseline="middle"
            class="donut-value"
            :opacity="hovered && hovered !== segment.label ? 0.35 : 1"
            @mouseenter="hovered = segment.label"
            @mouseleave="hovered = null"
          >
            {{ segment.labelText }}
          </text>
        </template>

        <!-- Estado vazio -->
        <text
          v-if="!segments.length"
          x="60"
          y="60"
          text-anchor="middle"
          dominant-baseline="middle"
          class="donut-empty"
        >
          Sem dados
        </text>
      </svg>
    </div>

    <!-- Legenda -->
    <div class="donut-legend">
      <button
        v-for="item in items"
        :key="item.label"
        type="button"
        class="donut-legend-item"
        :style="{
          opacity: hovered && hovered !== item.label ? 0.4 : 1,
        }"
        @mouseenter="hovered = item.label"
        @mouseleave="hovered = null"
      >
        <span class="donut-legend-dot" :style="{ backgroundColor: item.color }" />

        <span>
          {{ item.label }}
        </span>

        <strong v-if="showLegendValues"> {{ formatValue(item.value) }}{{ suffix }} </strong>
      </button>
    </div>
  </div>
</template>

<style scoped>
.donut-chart {
  width: 100%;
  min-height: 330px;

  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;

  gap: 12px;
}

/*
 * Área visual principal.
 * O tamanho fica padronizado no próprio componente.
 */
.donut-visual {
  width: min(100%, 290px);
  height: 240px;

  display: flex;
  align-items: center;
  justify-content: center;
}

.donut-visual svg {
  display: block;

  width: 100%;
  height: 100%;

  overflow: visible;
}

/*
 * Transição dos segmentos.
 */
.donut-segment {
  cursor: pointer;

  transition:
    opacity 0.15s ease,
    filter 0.15s ease;
}

.donut-segment:hover {
  filter: brightness(1.04);
}

/*
 * Percentuais exibidos ao redor do gráfico.
 */
.donut-value {
  font-size: 8px;
  font-weight: 500;

  cursor: default;

  transition: opacity 0.15s ease;
}

/*
 * Legenda inferior.
 */
.donut-legend {
  width: 100%;

  display: flex;
  align-items: center;
  justify-content: center;

  flex-wrap: wrap;

  gap: 8px 14px;
}

.donut-legend-item {
  border: 0;
  padding: 0;

  background: transparent;

  display: inline-flex;
  align-items: center;

  gap: 5px;

  color: #667085;

  font: inherit;
  font-size: 12px;

  cursor: default;

  transition: opacity 0.15s ease;
}

.donut-legend-item strong {
  margin-left: 2px;

  color: #344054;

  font-weight: 700;
}

.donut-legend-dot {
  width: 9px;
  height: 9px;

  flex: 0 0 9px;

  border-radius: 999px;
}

.donut-empty {
  fill: #98a2b3;

  font-size: 7px;
  font-weight: 600;
}

/*
 * Responsividade.
 */
@media (max-width: 768px) {
  .donut-chart {
    min-height: 285px;
  }

  .donut-visual {
    width: min(100%, 250px);
    height: 210px;
  }

  .donut-value {
    font-size: 7.5px;
  }

  .donut-legend-item {
    font-size: 11px;
  }
}
</style>
