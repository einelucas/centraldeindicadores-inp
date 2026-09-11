/** Tipos do módulo RNC (Registro de Não Conformidade) usados na importação no navegador. */

import type { PeriodRange } from "~/logic/lib/period";

export interface RncNormalizedRecord {
  statusRnc: string;
  unidade: string;
  dataCriacao: Date;
  dataSolucao: Date | null;
  tempoTratativa: number | null;
  ofensor: string;
  year: number;
  month: number; // 1..12 (mês de criação)
  raw: Record<string, unknown>;
}

export interface RncMonthAggregate {
  label: string;
  year: number;
  month: number;
  chamados: number;
  solucionados: number;
  diasMedios: number | null;
  dentroMeta: boolean | null;
}

export interface RncUnitAggregate {
  name: string;
  criadas: number;
  tratadas: number;
  aderencia: number;
  temposTratativa: number[];
  diasMedios: number | null;
  diasMedianos: number | null;
  tratativasComTempo: number;
  maiorTempoTratativa: number | null;
  principalOfensor: string | null;
  principalOfensorCount: number;
  excluded: boolean;
}

export interface RncOfensorAggregate {
  name: string;
  count: number;
  pct: number;
}

export interface RncResult {
  metaDias: number;
  excludedUnits: string[];
  period: PeriodRange | null;
  totalCriadas: number;
  totalTratadas: number;
  aderenciaTotal: number;
  resultadoDias: number | null;
  months: RncMonthAggregate[];
  units: RncUnitAggregate[];
  ofensores: RncOfensorAggregate[];
}

export const RNC_DEFAULT_MAX_DIAS = 15;

/** Colunas obrigatórias normalizadas. */
export const REQUIRED_RNC_COLS = [
  "status_rnc",
  "unidade",
  "data_de_criação",
  "data_de_solução",
  "tempo_de_tratativa",
  "ofensor",
] as const;

export type { PeriodRange };
