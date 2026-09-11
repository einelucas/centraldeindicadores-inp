import type { AvailablePeriod, PeriodRange } from "~/types/api";
import { MONTH_NAMES } from "~/utils/dates";

export const MONTHS = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
] as const;

export type Semester = "S1" | "S2";
export interface MonthReference { year: number; month: number }

/** Índice inteiro contínuo de um mês — compara/ordena intervalos entre anos. */
export function toMonthIndex(year: number, month: number): number {
  return year * 12 + (month - 1);
}

/** Troca início/fim se o intervalo estiver invertido. Porte de normalizePeriodRange. */
export function normalizePeriodRange(range: PeriodRange): PeriodRange {
  const startIdx = toMonthIndex(range.startYear, range.startMonth);
  const endIdx = toMonthIndex(range.endYear, range.endMonth);
  if (startIdx <= endIdx) return range;
  return { startYear: range.endYear, startMonth: range.endMonth, endYear: range.startYear, endMonth: range.startMonth };
}

/** `true` sempre que `range` for `null`/`undefined` (sem restrição = "Tudo"). */
export function isWithinPeriodRange(year: number, month: number, range: PeriodRange | null | undefined): boolean {
  if (!range) return true;
  const n = normalizePeriodRange(range);
  const idx = toMonthIndex(year, month);
  return idx >= toMonthIndex(n.startYear, n.startMonth) && idx <= toMonthIndex(n.endYear, n.endMonth);
}

/** Lista ordenada de {year, month} do início ao fim do intervalo, inclusive. */
export function enumeratePeriodMonths(range: PeriodRange): MonthReference[] {
  const n = normalizePeriodRange(range);
  const startIdx = toMonthIndex(n.startYear, n.startMonth);
  const endIdx = toMonthIndex(n.endYear, n.endMonth);
  const months: MonthReference[] = [];
  for (let idx = startIdx; idx <= endIdx; idx++) {
    months.push({ year: Math.floor(idx / 12), month: (((idx % 12) + 12) % 12) + 1 });
  }
  return months;
}

/** Classifica uma competência mensal no período operacional (Ano + Semestre).
 * Dezembro pertence ao S1 do ano SEGUINTE; janeiro-maio ao S1 do próprio ano;
 * junho-novembro ao S2 do próprio ano. Porte de getOperationalPeriod. */
export function getOperationalPeriod(year: number, month: number): { periodYear: number; semester: Semester } {
  if (!Number.isInteger(year) || !Number.isInteger(month) || month < 1 || month > 12) {
    throw new RangeError("Competência mensal inválida.");
  }
  if (month === 12) return { periodYear: year + 1, semester: "S1" };
  if (month <= 5) return { periodYear: year, semester: "S1" };
  return { periodYear: year, semester: "S2" };
}

/** Ano do período + Semestre -> intervalo de meses. Para S1, `periodYear` é
 * sempre o ano de TÉRMINO (maio). Porte de cycleFromYearSemester. */
export function cycleFromYearSemester(periodYear: number, semester: Semester): PeriodRange {
  return semester === "S2"
    ? { startYear: periodYear, startMonth: 6, endYear: periodYear, endMonth: 11 }
    : { startYear: periodYear - 1, startMonth: 12, endYear: periodYear, endMonth: 5 };
}

/** Inverso de cycleFromYearSemester. */
export function yearSemesterFromCycle(cycle: PeriodRange): { year: number; semester: Semester } {
  return { year: cycle.endYear, semester: cycle.startMonth === 12 ? "S1" : "S2" };
}

/** Ciclo operacional (intervalo de meses) que contém a competência informada. */
export function cycleForMonth(year: number, month: number): PeriodRange {
  const { periodYear, semester } = getOperationalPeriod(year, month);
  return cycleFromYearSemester(periodYear, semester);
}

/** Ciclo semestral ativo na data de referência — atalho "Ciclo atual". */
export function getCurrentCycle(reference: Date = new Date()): PeriodRange {
  return cycleForMonth(reference.getFullYear(), reference.getMonth() + 1);
}

/** Próximo semestre cronológico após Ano do período + Semestre informados. */
export function nextPeriod(periodYear: number, semester: Semester): { year: number; semester: Semester } {
  return semester === "S1" ? { year: periodYear, semester: "S2" } : { year: periodYear + 1, semester: "S1" };
}

/** Ex.: "2027 S1 · Dez/26 - Mai/27". */
export function formatPeriodOptionLabel(periodYear: number, semester: Semester): string {
  const cycle = cycleFromYearSemester(periodYear, semester);
  const start = `${MONTH_NAMES[cycle.startMonth - 1]}/${String(cycle.startYear).slice(-2)}`;
  const end = `${MONTH_NAMES[cycle.endMonth - 1]}/${String(cycle.endYear).slice(-2)}`;
  return `${periodYear} ${semester} · ${start} - ${end}`;
}

/** Ex.: "Dez/2026 – Mai/2027". Retorna "Tudo" quando `range` é `null`. */
export function formatPeriodRangeLabel(range: PeriodRange | null | undefined, monthNames: readonly string[] = MONTH_NAMES): string {
  if (!range) return "Tudo";
  const n = normalizePeriodRange(range);
  const start = `${monthNames[n.startMonth - 1] ?? n.startMonth}/${n.startYear}`;
  const end = `${monthNames[n.endMonth - 1] ?? n.endMonth}/${n.endYear}`;
  return `${start} – ${end}`;
}

export function operationalPeriod(referenceYear: number, semester: "S1" | "S2"): PeriodRange {
  return semester === "S1"
    ? { startYear: referenceYear - 1, startMonth: 12, endYear: referenceYear, endMonth: 5 }
    : { startYear: referenceYear, startMonth: 6, endYear: referenceYear, endMonth: 11 };
}

export function periodToQuery(period: PeriodRange | null | undefined): Record<string, number> {
  if (!period) return {};
  return {
    periodStartYear: period.startYear,
    periodStartMonth: period.startMonth,
    periodEndYear: period.endYear,
    periodEndMonth: period.endMonth,
  };
}

export function periodLabel(period: PeriodRange | null | undefined): string {
  if (!period) return "Todos os períodos";
  return `${MONTHS[period.startMonth - 1]}/${period.startYear} – ${MONTHS[period.endMonth - 1]}/${period.endYear}`;
}

export function periodFromAvailable(item: AvailablePeriod): PeriodRange {
  const first = item.competencies[0];
  const last = item.competencies.at(-1);
  return {
    startYear: first?.year ?? item.referenceYear,
    startMonth: first?.month ?? item.monthStart,
    endYear: last?.year ?? item.referenceYear,
    endMonth: last?.month ?? item.monthEnd,
  };
}

export function currentOperationalPeriod(date = new Date()): PeriodRange {
  const month = date.getMonth() + 1;
  const year = date.getFullYear();
  if (month >= 6 && month <= 11) return operationalPeriod(year, "S2");
  return operationalPeriod(month === 12 ? year + 1 : year, "S1");
}
