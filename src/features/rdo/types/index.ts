/**
 * Tipos do módulo RDO (Relatório Diário de Obra).
 * Mantidos apenas para a exportação em PDF consolidado do Scorecard
 * (@/features/scorecard/exports/pdf e @/features/scorecard/components/ScorecardView),
 * que ainda depende do formato de resultado do RDO. O restante do módulo RDO
 * foi migrado para o Nuxt.
 */

import type { PeriodRange } from "@/lib/period";

/** Agregado por unidade. */
export interface RdoUnitAggregate {
  name: string;
  emitidos: number;
  aprovados: number;
  aderencia: number;
  excluded: boolean;
}

/** Agregado por mês. */
export interface RdoMonthAggregate {
  label: string;
  year: number;
  month: number; // 0-based (Date.getMonth), como no HTML
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
