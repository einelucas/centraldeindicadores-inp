import type { AvailablePeriod, PeriodRange } from "~/types/api";

export const MONTHS = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
] as const;

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
