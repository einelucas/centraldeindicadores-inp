import type { PeriodRange } from "@/lib/period";

/**
 * Formato do payload publicado do RDO. Mantido apenas porque
 * @/features/scorecard/publications ainda lê publicações antigas do RDO ao
 * montar o Painel Geral consolidado. O restante do módulo RDO foi migrado
 * para o Nuxt.
 */
export interface RdoPublishedUnit {
  n: string;
  v: number;
}

export interface RdoPublishedMonth {
  label: string;
  v: number | null;
}

export interface RdoPublishedPayload {
  pontos: number;
  peso: number;
  meta: number;
  resultado: number;
  aprovados: number;
  emitidos: number;
  emRevisaoPct: number;
  preenchendoPct: number;
  /** Intervalo de período usado no cálculo publicado; `null` = sem restrição. */
  periodo?: PeriodRange | null;
  unidades: RdoPublishedUnit[];
  mensal: RdoPublishedMonth[];
}
