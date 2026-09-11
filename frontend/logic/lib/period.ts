/**
 * Intervalo de período livre (de mês/ano até mês/ano), compartilhado pelos
 * importadores/exportadores portados do módulo original. Representa "sem
 * restrição" como `null` — nunca como um intervalo aberto implícito.
 *
 * Nota: esta é a cópia usada pela lógica de importação/exportação pura
 * (browser). O restante do app Nuxt usa `~/utils/period.ts`, que expõe as
 * mesmas regras de negócio adaptadas ao tipo `PeriodRange` de `~/types/api`.
 */

export interface PeriodRange {
  startYear: number;
  startMonth: number; // 1-12
  endYear: number;
  endMonth: number; // 1-12
}

export interface MonthReference {
  year: number;
  month: number;
}

/** Índice inteiro contínuo de um mês, usado para comparar/ordenar intervalos mesmo entre anos. */
export function toMonthIndex(year: number, month: number): number {
  return year * 12 + (month - 1);
}

/** Troca início/fim se o intervalo estiver invertido. */
export function normalizePeriodRange(range: PeriodRange): PeriodRange {
  const startIdx = toMonthIndex(range.startYear, range.startMonth);
  const endIdx = toMonthIndex(range.endYear, range.endMonth);
  if (startIdx <= endIdx) return range;
  return {
    startYear: range.endYear,
    startMonth: range.endMonth,
    endYear: range.startYear,
    endMonth: range.startMonth,
  };
}

/** `true` sempre que `range` for `null`/`undefined` (nenhuma restrição = "Tudo"). */
export function isWithinPeriodRange(
  year: number,
  month: number,
  range: PeriodRange | null | undefined,
): boolean {
  if (!range) return true;
  const normalized = normalizePeriodRange(range);
  const idx = toMonthIndex(year, month);
  return (
    idx >= toMonthIndex(normalized.startYear, normalized.startMonth) &&
    idx <= toMonthIndex(normalized.endYear, normalized.endMonth)
  );
}
