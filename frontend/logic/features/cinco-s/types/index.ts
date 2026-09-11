/** Tipos do módulo 5S usados na importação no navegador. */

/** Área auditada dentro de uma unidade. */
export interface FiveSArea {
  divisao: string | null;
  area: string;
  meta: number;
  nota: number;
}

/** Registro 5S normalizado: uma unidade num mês, com suas áreas. */
export interface FiveSNormalizedRecord {
  unit: string;
  year: number;
  month: number; // 1..12
  areas: FiveSArea[];
  raw: Record<string, unknown>;
}
