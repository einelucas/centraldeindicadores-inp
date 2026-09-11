/** Tipos do módulo IDP baseado nos Relatórios Semanais de Obra (RSO), usados na leitura do PDF no navegador. */

export const IDP_DISC_NAMES = [
  "01 - Civil",
  "02 - Mecânica",
  "03 - Mecânica de Rotativos",
  "04 - Elétrica",
  "05 - Instrumentação",
  "06 - Automação",
  "07 - Isolamento",
  "08 - Válvulas Manuais",
] as const;

export interface IdpRsoAreaValue {
  area: string;
  prevAcum: number;
  realAcum: number;
}

export type IdpRsoDisciplineData = Record<string, IdpRsoAreaValue[]>;

export interface IdpExecutionPhase {
  label: string;
  prevAcum: number;
  realAcum: number;
}

export type IdpReferenceSource = "PDF_MES_REF" | "MANUAL" | "UNRESOLVED";

/**
 * Um registro representa uma versão semanal completa do RSO de uma unidade.
 * O número do RSO identifica a versão; competência, período e emissão são
 * dimensões independentes e nunca substituem umas às outras silenciosamente.
 */
export interface IdpNormalizedRecord {
  unit: string;
  detectedUnit: string | null;
  unitAdjusted: boolean;

  rsoNumero: number | null;
  detectedRsoNumero: number | null;
  rsoAdjusted: boolean;

  referenceYear: number | null;
  referenceMonth: number | null;
  detectedReferenceYear: number | null;
  detectedReferenceMonth: number | null;
  referenceSource: IdpReferenceSource;
  referenceOriginalText: string | null;
  referenceAdjusted: boolean;

  periodStart: string | null;
  periodEnd: string | null;
  emissionDate: string | null;

  fileName: string;
  areas: string[];
  discData: IdpRsoDisciplineData;
  execucaoFases: IdpExecutionPhase[];
  raw: Record<string, unknown>;
}

/**
 * Formato calculado pelo FastAPI (`GET /api/v1/idp` e `.result`) — usado
 * pela administração, exportação em PDF e publicação. Independente de
 * `IdpNormalizedRecord` (formato bruto lido do PDF no navegador).
 */
export interface IdpUnitDisciplineDetail {
  disciplina: string;
  prevAvg: number;
  realAvg: number;
  aderencia: number | null;
  areas: IdpRsoAreaValue[];
}

export interface IdpDisciplineUnitGroup {
  unit: string;
  prevAvg: number;
  realAvg: number;
  aderencia: number | null;
  entries: IdpRsoAreaValue[];
}

export interface IdpUnitRow {
  unit: string;
  rsoNumero: number;
  referenceYear: number;
  referenceMonth: number;
  referenceSource: IdpReferenceSource;
  referenceOriginalText: string | null;
  referenceAdjusted: boolean;
  periodStart: string | null;
  periodEnd: string | null;
  emissionDate: string | null;
  fileName: string;
  nFases: number;
  prevAcum: number;
  realAcum: number;
  aderencia: number | null;
  excluded: boolean;
  phases: IdpExecutionPhase[];
  disciplines: IdpUnitDisciplineDetail[];
}

export interface IdpDisciplineRow {
  disciplina: string;
  prevAvg: number | null;
  realAvg: number | null;
  aderencia: number | null;
  unitGroups: IdpDisciplineUnitGroup[];
}

export interface IdpMonthAggregate {
  year: number;
  month: number;
  label: string;
  aderencia: number | null;
  activeDocuments: number;
  totalPrevistoMedio: number;
  totalRealMedio: number;
}

export interface IdpResult {
  threshold: number;
  excludedDisciplines: string[];
  excludedUnits: string[];
  selectedYear: number;
  selectedMonth: number;
  historyStartYear: number;
  historyMonthStart: number;
  historyEndYear: number;
  historyMonthEnd: number;
  activeDocuments: number;
  aderenciaGeral: number | null;
  totalPrevistoMedio: number;
  totalRealMedio: number;
  unitRows: IdpUnitRow[];
  disciplineRows: IdpDisciplineRow[];
  monthly: IdpMonthAggregate[];
}
