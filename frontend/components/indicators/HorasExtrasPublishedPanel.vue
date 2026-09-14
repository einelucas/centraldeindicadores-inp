<script setup lang="ts">
import {
  Building2,
  ChartLine,
  Construction,
  Percent,
  Scale,
  Target,
} from "lucide-vue-next";

import type { PeriodRange } from "~/types/api";
import { useReadingContextCycle } from "~/composables/useReadingContextCycle";
import { yearSemesterFromCycle } from "~/utils/period";

const selectedUnit = ref("all");

const { cycle, setPeriod } = useReadingContextCycle();

const period = computed<PeriodRange>({
  get: () => cycle.value,
  set: (range) => {
    const { year, semester } = yearSemesterFromCycle(range);
    setPeriod(year, semester);
  },
});

const performanceRanges = [
  {
    label: "Faixa 100%",
    condition: "≤ 1%",
    description: "Meta de referência informada para o indicador.",
    tone: "success",
  },
  {
    label: "Faixa 80%",
    condition: "> 1% e ≤ 2%",
    description: "Faixa de desempenho já informada no alinhamento.",
    tone: "warning",
  },
  {
    label: "Demais faixas",
    condition: "> 2%",
    description: "Aguardando definição completa da matriz de pontuação.",
    tone: "pending",
  },
] as const;
</script>

<template>
  <div class="stack painel-frontend horas-extras-preview">
    <div class="surface">
      <div class="surface-header">
        <div>
          <h2>Horas Extras Pagas</h2>
          <p>Estrutura do painel preparada · integração de dados em desenvolvimento</p>
        </div>

        <div class="toolbar">
          <PeriodSelector v-model="period" />
          <UnitSelector v-model="selectedUnit" :units="[]" />
        </div>
      </div>

      <div class="development-banner">
        <Construction :size="18" />
        <div>
          <strong>Indicador em desenvolvimento</strong>
          <span>
            O peso de 10% permanece reservado no Scorecard, mas este módulo ainda
            não gera pontuação nem altera o resultado consolidado.
          </span>
        </div>
      </div>

      <div class="surface-body">
        <div class="mgrid">
          <div class="mc reference-card">
            <div class="mc-head">
              <div class="ml">Meta de referência</div>
              <div class="mc-icon"><Target :size="16" /></div>
            </div>
            <div class="mv">≤ 1%</div>
            <div class="mm">Quanto menor, melhor</div>
            <div class="ms neutral-status">Regra de negócio informada</div>
          </div>

          <div class="mc warning-card">
            <div class="mc-head">
              <div class="ml">Faixa 80%</div>
              <div class="mc-icon"><Percent :size="16" /></div>
            </div>
            <div class="mv">&gt; 1% e ≤ 2%</div>
            <div class="mm">Segunda faixa conhecida</div>
            <div class="ms neutral-status">Matriz parcial</div>
          </div>

          <div class="mc reserved-card">
            <div class="mc-head">
              <div class="ml">Peso no Scorecard</div>
              <div class="mc-icon"><Scale :size="16" /></div>
            </div>
            <div class="mv">10%</div>
            <div class="mm">Peso oficial reservado</div>
            <div class="ms neutral-status">Não contabilizado</div>
          </div>

          <div class="mc development-card">
            <div class="mc-head">
              <div class="ml">Direção</div>
              <div class="mc-icon"><ChartLine :size="16" /></div>
            </div>
            <div class="mv">MENOR</div>
            <div class="mm">Unidade prevista: %</div>
            <div class="ms neutral-status">Aguardando fonte de dados</div>
          </div>
        </div>

        <div class="card indicator-card">
          <div class="ph">Horas Extras Pagas</div>

          <p class="ps horas-extras-summary">
            <span class="summary-target">META DE REFERÊNCIA: ≤ 1%</span>
            <span>Direção: <strong>quanto menor, melhor</strong></span>
            <span class="summary-muted">
              — o resultado real será exibido após a definição do modelo de planilha
              e da fórmula oficial.
            </span>
          </p>

          <div class="g2 indicator-subgrid">
            <div class="indicator-subcard">
              <div class="ct">Evolução mensal</div>
              <div class="cs">
                Percentual mensal de horas extras comparado com a meta e as faixas
                de desempenho.
              </div>

              <div class="preview-placeholder">
                <ChartLine :size="32" />
                <strong>Gráfico preparado para integração</strong>
                <span>
                  Quando a fonte de dados for definida, esta área exibirá a evolução
                  mensal com referência em 1% e 2%.
                </span>
              </div>
            </div>

            <div class="indicator-subcard">
              <div class="ct">Faixas de desempenho</div>
              <div class="cs">
                Regras conhecidas do indicador, sem antecipar faixas ainda não
                definidas.
              </div>

              <div class="performance-ranges">
                <div
                  v-for="range in performanceRanges"
                  :key="range.label"
                  :class="['range-row', `range-${range.tone}`]"
                >
                  <div>
                    <strong>{{ range.label }}</strong>
                    <span>{{ range.description }}</span>
                  </div>
                  <b>{{ range.condition }}</b>
                </div>
              </div>
            </div>
          </div>

          <div class="indicator-subcard">
            <div class="ct">Horas extras por unidade</div>
            <div class="cs">
              Comparativo entre unidades seguindo o mesmo padrão visual dos demais
              indicadores.
            </div>

            <div class="preview-placeholder compact">
              <Building2 :size="28" />
              <strong>Comparativo por unidade aguardando dados</strong>
              <span>
                O filtro de unidade será habilitado quando a planilha oficial
                definir como cada unidade será identificada.
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.development-banner {
  margin: 0 24px;
  padding: 12px 14px;
  display: flex;
  gap: 10px;
  align-items: flex-start;
  border: 1px solid #d8e1ec;
  border-radius: 10px;
  background: #f5f8fc;
  color: #304f7e;
}

.development-banner > div {
  display: grid;
  gap: 2px;
}

.development-banner strong {
  font-size: 13px;
}

.development-banner span {
  color: #637083;
  font-size: 12px;
  line-height: 1.45;
}

.reference-card {
  border-left-color: #609346 !important;
}

.warning-card {
  border-left-color: #eaa239 !important;
}

.reserved-card {
  border-left-color: #304f7e !important;
}

.development-card {
  border-left-color: #8a94a3 !important;
}

.reference-card .mv {
  color: #609346;
}

.warning-card .mv {
  color: #c57f18;
  font-size: clamp(20px, 2vw, 28px);
}

.reserved-card .mv {
  color: #304f7e;
}

.development-card .mv {
  color: #596579;
  font-size: clamp(20px, 2vw, 28px);
}

.neutral-status {
  color: #6d7787;
}

.horas-extras-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  align-items: center;
}

.summary-target {
  color: #304f7e;
  font-weight: 700;
}

.summary-muted {
  color: #8a8f98;
}

.preview-placeholder {
  min-height: 235px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 28px;
  text-align: center;
  border: 1px dashed #cbd4df;
  border-radius: 10px;
  background: #fafbfd;
  color: #7a8594;
}

.preview-placeholder strong {
  color: #465469;
  font-size: 14px;
}

.preview-placeholder span {
  max-width: 440px;
  font-size: 12px;
  line-height: 1.5;
}

.preview-placeholder.compact {
  min-height: 150px;
}

.performance-ranges {
  display: grid;
  gap: 10px;
  margin-top: 18px;
}

.range-row {
  min-height: 70px;
  padding: 12px 14px;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  border: 1px solid #e1e6ec;
  border-left-width: 4px;
  border-radius: 9px;
  background: #fff;
}

.range-row > div {
  display: grid;
  gap: 3px;
}

.range-row strong {
  font-size: 13px;
  color: #2f3d51;
}

.range-row span {
  font-size: 11px;
  line-height: 1.4;
  color: #7a8594;
}

.range-row b {
  white-space: nowrap;
  font-size: 14px;
  color: #2f3d51;
}

.range-success {
  border-left-color: #609346;
}

.range-warning {
  border-left-color: #eaa239;
}

.range-pending {
  border-left-color: #aab2bd;
}

@media (max-width: 760px) {
  .development-banner {
    margin: 0 14px;
  }

  .range-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .preview-placeholder {
    min-height: 200px;
    padding: 22px 16px;
  }
}
</style>
