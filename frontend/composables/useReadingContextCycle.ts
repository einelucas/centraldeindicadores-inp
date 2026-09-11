import { cycleFromYearSemester, getCurrentCycle, periodToQuery, yearSemesterFromCycle, type Semester } from "~/utils/period";
import type { PeriodRange } from "~/types/api";

export function periodQueryString(period: PeriodRange): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(periodToQuery(period))) {
    params.set(key, String(value));
  }
  return params.toString();
}

/**
 * @param initialPeriod Período salvo a usar como valor inicial em vez do
 * ciclo vigente na data real — usado só pelo Scorecard (período persistido no
 * servidor). Os demais módulos não passam esse argumento.
 */
export function useReadingContextCycle(initialPeriod?: PeriodRange | null) {
  const current = yearSemesterFromCycle(getCurrentCycle());
  const initial = initialPeriod ? yearSemesterFromCycle(initialPeriod) : current;
  const year = ref(initial.year);
  const semester = ref<Semester>(initial.semester);
  const cycle = computed(() => cycleFromYearSemester(year.value, semester.value));
  const isCurrent = computed(() => year.value === current.year && semester.value === current.semester);

  function setPeriod(nextYear: number, nextSemester: Semester) {
    year.value = nextYear;
    semester.value = nextSemester;
  }

  return { year, semester, cycle, isCurrent, setPeriod };
}
