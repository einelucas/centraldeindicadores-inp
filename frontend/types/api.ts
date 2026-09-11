export type Role = "VIEWER" | "ANALYST" | "ADMIN";

export type Permission =
  | "indicators:read"
  | "indicators:export"
  | "indicators:edit"
  | "indicators:publish"
  | "import:run"
  | "import:read"
  | "users:manage"
  | "audit:read"
  | "settings:manage";

export interface CurrentUser {
  id: string;
  email: string;
  name: string;
  role: Role;
  active: boolean;
}

export interface PeriodRange {
  startYear: number;
  startMonth: number;
  endYear: number;
  endMonth: number;
}

export interface AvailablePeriod {
  periodKey: string;
  referenceYear: number;
  semester: "S1" | "S2";
  monthStart: number;
  monthEnd: number;
  competencies: Array<{ year: number; month: number }>;
  label: string;
}

export interface Publication<TPayload extends Record<string, unknown> = Record<string, unknown>> {
  id: string;
  version: number;
  target: number | null;
  result: number | null;
  status: string | null;
  payload: TPayload;
  active?: boolean;
  publishedAt: string;
  publishedBy: { id: string; name: string; email: string };
  cycleYear?: number | null;
  cycleSemester?: string | null;
}

export interface PublicationEnvelope<TPayload extends Record<string, unknown> = Record<string, unknown>> {
  publication: Publication<TPayload> | null;
  historyCount?: number;
}

export interface ApiProblem {
  detail?: string | Array<{ msg?: string }>;
  message?: string;
  error?: string;
}

export interface ImportJob {
  id: string;
  module: string;
  fileName: string;
  referenceYear: number | null;
  referenceMonth: number | null;
  status: string;
  totalFound: number;
  totalInserted: number;
  totalIgnored: number;
  totalUpdated: number;
  totalRejected: number;
  startedAt: string;
  completedAt: string | null;
  userId: string;
  batches: ImportBatch[];
}

export interface ImportBatch {
  id: string;
  batchNumber: number;
  totalReceived: number;
  totalInserted: number;
  totalIgnored: number;
  totalUpdated: number;
  totalRejected: number;
  processedAt: string;
}

export interface UploadRowError {
  row: number | null;
  field: string | null;
  message: string;
}

export interface UploadFileResult {
  fileName: string;
  found: number;
  accepted: number;
  rejected: number;
  errors: UploadRowError[];
}

export interface UploadImportTotals {
  found: number;
  inserted: number;
  ignored: number;
  updated: number;
  rejected: number;
}

/** Resposta de `POST /importacoes/{modulo}/arquivos` — parsing/validação/
 * normalização/dedup/persistência acontecem inteiramente no FastAPI; o
 * Nuxt só envia os arquivos originais e exibe este resultado consolidado. */
export interface UploadImportResult {
  importJobId: string;
  status: string;
  totals: UploadImportTotals;
  files: UploadFileResult[];
  durationMs: number;
}

export interface MetricDefinition {
  key: string;
  label: string;
  format?: "number" | "percent" | "decimal" | "days";
}

export interface DashboardIndicator {
  key: string;
  label: string;
  shortLabel: string;
  peso: number;
  meta: number | null;
  direction: string | null;
  unit: string | null;
  result: number | null;
  hasData: boolean;
  passed: boolean | null;
  partial: number | null;
  partialPass: boolean | null;
  months: Array<{
    key: string;
    label: string;
    value: number | null;
    passed: boolean | null;
    pctOfMeta: number | null;
  }>;
  /** "active" | "development" — indicadores em desenvolvimento (ex.: Horas
   * Extras) nunca pontuam; ver `scoringEnabled`. */
  status: string;
  scoringEnabled: boolean;
}

export interface DashboardResponse extends PeriodRange {
  hasData: boolean;
  period: PeriodRange;
  periodKey: string;
  monthKeys: string[];
  monthLabels: string[];
  pontuacaoPrevista: number;
  pontuacaoPrevistaSemestre: number;
  pontosRealizados: number;
  atendimentoGeral: number;
  percentualSemestreCompleto: number;
  percentualDadosDisponiveis: number;
  /** `pontuacaoPrevista`, mas usando só o peso contabilizável (90% enquanto
   * Horas Extras estiver em desenvolvimento). */
  pontuacaoPrevistaContabilizavel: number;
  /** `pontuacaoPrevista - pontuacaoPrevistaContabilizavel`. */
  pontosReservados: number;
  /** `pontosRealizados / pontuacaoPrevistaContabilizavel * 100`. */
  atendimentoAtivosGeral: number;
  /** Percentual do peso oficial que é contabilizável hoje — 90.0. */
  coberturaAtivaPct: number;
  referenceDate: string | null;
  indicators: DashboardIndicator[];
}

export interface ScorecardRow {
  key: string;
  label: string;
  peso: number;
  meta: number | null;
  direction: string | null;
  unit: string | null;
  value: number | null;
  pass: boolean;
  pontos: number;
  pontosPossiveis: number;
  hasValue: boolean;
  status: string;
  scoringEnabled: boolean;
}

export interface ScorecardComputation {
  year: number;
  month: number;
  sourceValues: Record<string, number | null>;
  values: Record<string, number | null>;
  result: {
    rows: ScorecardRow[];
    totalPontos: number;
    totalPeso: number;
    pontosPossiveisMes: number;
    atendimentoMes: number;
    pontosOficiaisMes: number;
    pontosReservadosMes: number;
    coberturaAtivaPct: number;
  };
}
