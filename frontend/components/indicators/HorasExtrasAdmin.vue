<script setup lang="ts">
import {
  CheckCircle2,
  Construction,
  Database,
  FileSpreadsheet,
  Scale,
  Upload,
} from "lucide-vue-next";

const definedItems = [
  "Peso oficial de 10% reservado no Scorecard.",
  "Indicador com direção MENOR — quanto menor o percentual, melhor.",
  "Meta de referência informada: ≤ 1%.",
  "Faixa de 80% informada: > 1% e ≤ 2%.",
];

const pendingItems = [
  "Modelo oficial da planilha e identificação das colunas.",
  "Fórmula completa que transforma a base em percentual.",
  "Definição das faixas de pontuação acima de 2%.",
  "Regras de unidade, competência, duplicidade e tratamento de registros inválidos.",
];
</script>

<template>
  <div class="stack painel-frontend horas-extras-admin">
    <div class="surface">
      <div class="surface-header">
        <div>
          <h2>Horas Extras — Administração</h2>
          <p>Preparação da origem de dados, cálculo e publicação do indicador.</p>
        </div>

        <div class="admin-state">
          <Construction :size="16" />
          Em desenvolvimento
        </div>
      </div>

      <div class="surface-body">
        <div class="g2 indicator-subgrid">
          <div class="indicator-subcard">
            <div class="ct">Regras já definidas</div>
            <div class="cs">
              Informações que podem ser consideradas estáveis nesta fase.
            </div>

            <div class="admin-list">
              <div v-for="item in definedItems" :key="item" class="admin-list-item">
                <CheckCircle2 :size="17" />
                <span>{{ item }}</span>
              </div>
            </div>
          </div>

          <div class="indicator-subcard">
            <div class="ct">Pendências antes da ativação</div>
            <div class="cs">
              O módulo não deve pontuar enquanto estes itens não estiverem
              formalmente definidos.
            </div>

            <div class="admin-list pending">
              <div v-for="(item, index) in pendingItems" :key="item" class="admin-list-item">
                <span class="step-number">{{ index + 1 }}</span>
                <span>{{ item }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="indicator-subcard import-card">
          <div class="import-icon">
            <FileSpreadsheet :size="30" />
          </div>

          <div class="import-copy">
            <div class="ct">Importação da planilha</div>
            <div class="cs">
              A área de importação será habilitada assim que o layout oficial da
              base for recebido. Até lá, nenhum parser ou cálculo provisório será
              criado.
            </div>

            <div class="flow-row">
              <span><Upload :size="15" /> Importação</span>
              <i>→</i>
              <span><Database :size="15" /> Validação</span>
              <i>→</i>
              <span><Scale :size="15" /> Cálculo</span>
              <i>→</i>
              <span>Publicação</span>
            </div>
          </div>

          <button class="btn" type="button" disabled>
            <Upload :size="16" />
            Importar planilha
          </button>
        </div>

        <div class="activation-note">
          <strong>Proteção do Scorecard</strong>
          <p>
            Esta interface não altera a regra atual de pontuação: os 10% continuam
            reservados e não entram no cálculo final até que a implementação de
            Horas Extras seja validada e ativada no backend.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-state {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 8px 11px;
  border: 1px solid #d8e1ec;
  border-radius: 999px;
  background: #f5f8fc;
  color: #52647b;
  font-size: 12px;
  font-weight: 700;
}

.admin-list {
  display: grid;
  gap: 9px;
  margin-top: 18px;
}

.admin-list-item {
  display: flex;
  gap: 9px;
  align-items: flex-start;
  padding: 10px 11px;
  border: 1px solid #e3e7ec;
  border-radius: 8px;
  background: #fbfcfd;
  color: #526071;
  font-size: 12px;
  line-height: 1.45;
}

.admin-list-item svg {
  flex: 0 0 auto;
  margin-top: 1px;
  color: #609346;
}

.admin-list.pending .admin-list-item {
  background: #fffdf8;
}

.step-number {
  flex: 0 0 22px;
  height: 22px;
  display: inline-grid;
  place-items: center;
  border-radius: 999px;
  background: #eaa239;
  color: #fff;
  font-size: 11px;
  font-weight: 800;
}

.import-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
}

.import-icon {
  flex: 0 0 52px;
  height: 52px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: #eef3f9;
  color: #304f7e;
}

.import-copy {
  flex: 1 1 auto;
  min-width: 0;
}

.flow-row {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  align-items: center;
  margin-top: 13px;
  color: #768294;
  font-size: 11px;
}

.flow-row span {
  display: inline-flex;
  gap: 5px;
  align-items: center;
}

.flow-row i {
  font-style: normal;
  color: #a5aeba;
}

.import-card .btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.activation-note {
  padding: 14px 16px;
  border: 1px solid #d8e1ec;
  border-left: 4px solid #304f7e;
  border-radius: 9px;
  background: #f8fafc;
}

.activation-note strong {
  color: #304f7e;
  font-size: 13px;
}

.activation-note p {
  margin: 5px 0 0;
  color: #657184;
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 760px) {
  .import-card {
    align-items: flex-start;
    flex-direction: column;
  }

  .import-card .btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
