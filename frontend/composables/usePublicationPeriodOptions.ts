import { INDICATOR_DATA_CHANGED_EVENT } from "~/utils/browser-events";
import { getOperationalPeriod, toMonthIndex, type Semester } from "~/utils/period";
import type { AvailablePeriod } from "~/types/api";

export interface PeriodOption {
  year: number;
  semester: Semester;
}

export function periodOptionKey(year: number, semester: Semester): string {
  return `${year}:${semester}`;
}

/** "Jun, Jul e Ago" — usado na linha de cobertura mensal do card de contexto. */
export function joinWithAnd(items: string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} e ${items[items.length - 1]}`;
}

/**
 * Estado do seletor de "período de trabalho" de cada view de admin. Porte de
 * usePublicationPeriodOptions.ts (repositório de referência).
 *
 * Divergência de contrato conhecida: a referência filtra `/available-periods`
 * por `source` (módulo). O backend FastAPI atual (`GET /api/v1/available-periods`)
 * não aceita esse filtro — devolve os ciclos com dado em QUALQUER indicador
 * ativo do Scorecard, não só do módulo chamador. Documentado, não corrigido
 * silenciosamente (mudaria o contrato do backend, fora do escopo desta rodada).
 */
export function usePublicationPeriodOptions(_source: string, year: Ref<number> | number, semester: Ref<Semester> | Semester) {
  const api = useApi();
  const availablePeriods = ref<PeriodOption[]>([]);

  async function loadAvailablePeriods() {
    try {
      const body = await api.get<{ periods: AvailablePeriod[] }>("/available-periods");
      const next = body.periods.map((p) => ({ year: p.referenceYear, semester: p.semester as Semester }));
      availablePeriods.value = next;
      return next;
    } catch {
      return null;
    }
  }

  onMounted(() => {
    void loadAvailablePeriods();
    if (import.meta.client) window.addEventListener(INDICATOR_DATA_CHANGED_EVENT, loadAvailablePeriods);
  });
  onBeforeUnmount(() => {
    if (import.meta.client) window.removeEventListener(INDICATOR_DATA_CHANGED_EVENT, loadAvailablePeriods);
  });

  const currentPeriodHasData = computed(() => {
    const y = unref(year);
    const s = unref(semester);
    return availablePeriods.value.some((item) => item.year === y && item.semester === s);
  });

  const periodOptions = computed(() => {
    const y = unref(year);
    const s = unref(semester);
    const base = currentPeriodHasData.value ? availablePeriods.value : [...availablePeriods.value, { year: y, semester: s }];
    return base.slice().sort((a, b) => {
      const startA = a.semester === "S2" ? toMonthIndex(a.year, 6) : toMonthIndex(a.year - 1, 12);
      const startB = b.semester === "S2" ? toMonthIndex(b.year, 6) : toMonthIndex(b.year - 1, 12);
      return startB - startA;
    });
  });

  /** Depois de uma gravação bem-sucedida: se todos os registros pertencem a
   * um único período sem dado antes desta gravação, chama `setPeriod` e
   * retorna a mensagem de aviso; senão retorna `null`. */
  function detectNewPeriod(
    records: ReadonlyArray<{ year: number; month: number }>,
    setPeriod: (year: number, semester: Semester) => void,
  ): string | null {
    const periodsBeforeImport = availablePeriods.value;
    const keys = new Set(
      records.map((record) => {
        const period = getOperationalPeriod(record.year, record.month);
        return periodOptionKey(period.periodYear, period.semester);
      }),
    );
    if (keys.size !== 1) return null;
    const [key] = keys;
    const [yearText, semesterText] = (key ?? "").split(":");
    const periodYear = Number(yearText);
    const periodSemester = semesterText as Semester;
    const isNewPeriod = !periodsBeforeImport.some((item) => periodOptionKey(item.year, item.semester) === key);
    if (!isNewPeriod) return null;
    setPeriod(periodYear, periodSemester);
    return `Novo período detectado: ${formatPeriodOptionLabel(periodYear, periodSemester)}.`;
  }

  return { availablePeriods, periodOptions, currentPeriodHasData, loadAvailablePeriods, detectNewPeriod };
}

/** Próximo semestre cronológico — usado por "Preparar próximo semestre". */
export function nextWorkingPeriod(year: number, semester: Semester): PeriodOption {
  return nextPeriod(year, semester);
}
