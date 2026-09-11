/** Tipos do módulo RDO (Relatório Diário de Obra) usados pela importação/exportação no navegador. */

import type { PeriodRange } from "~/logic/lib/period";

/** Registro RDO normalizado, pronto para persistência. */
export interface RdoNormalizedRecord {
  dataReferencia: Date;
  empresaNome: string;
  statusDescricao: string;
  relatorioId: string | null;
  grupo: string | null;
  disciplina: string | null;
  year: number;
  month: number; // 1..12
  /** Linha original (headers normalizados) para exibição/auditoria. */
  raw: Record<string, unknown>;
}

/** Agregado por unidade. */
export interface RdoUnitAggregate {
  name: string;
  /** Código normalizado (gerado no servidor) — é o que `excludedUnits`
   * realmente guarda. Usar `name` (rótulo de exibição) para (des)marcar
   * exclusão não funciona, pois os dois nem sempre coincidem. */
  code: string;
  emitidos: number;
  aprovados: number;
  aderencia: number;
  excluded: boolean;
}

/** Agregado por mês. */
export interface RdoMonthAggregate {
  label: string;
  year: number;
  month: number; // 0-based (Date.getMonth), como no HTML original
  emitidos: number;
  aprovados: number;
  aderencia: number;
}

/** Resultado consolidado do RDO. */
export interface RdoResult {
  threshold: number;
  excludedUnits: string[];
  period: PeriodRange | null;
  totalEmitidos: number;
  totalAprovados: number;
  totalRevisar: number;
  totalPreenchendo: number;
  units: RdoUnitAggregate[];
  unitAvg: number;
  months: RdoMonthAggregate[];
}

/** Meta oficial de aprovação do RDO: 80%. Peso/pontuação do Scorecard vivem
 * apenas no backend (`backend/app/modules/scorecard/types.py`) — nunca
 * duplicar esses valores aqui. */
export const RDO_DEFAULT_TARGET = 0.8;

/** Colunas obrigatórias (normalizadas). Migrado de REQUIRED_RDO_COLS. */
export const REQUIRED_RDO_COLS = ["data", "status_descricao", "empresa_nome"] as const;

/** Status reconhecidos pelo cálculo (texto exato do sistema de origem). */
export const RDO_STATUS = {
  APROVADO: "Aprovado",
  REVISAR: "Revisar Relatório",
  PREENCHENDO: "Preenchendo Relatório",
} as const;
