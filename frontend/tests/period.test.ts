import { describe, expect, it } from "vitest";
import { currentOperationalPeriod, operationalPeriod, periodToQuery } from "~/utils/period";

describe("períodos operacionais", () => {
  it("mapeia S1 para dezembro do ano anterior até maio do ano de referência", () => {
    expect(operationalPeriod(2027, "S1")).toEqual({
      startYear: 2026,
      startMonth: 12,
      endYear: 2027,
      endMonth: 5,
    });
  });

  it("mapeia S2 para junho até novembro do mesmo ano", () => {
    expect(operationalPeriod(2027, "S2")).toEqual({
      startYear: 2027,
      startMonth: 6,
      endYear: 2027,
      endMonth: 11,
    });
  });

  it("considera dezembro como início do S1 seguinte", () => {
    expect(currentOperationalPeriod(new Date(2026, 11, 10))).toEqual(operationalPeriod(2027, "S1"));
  });

  it("serializa o contrato camelCase esperado pelo FastAPI", () => {
    expect(periodToQuery(operationalPeriod(2027, "S1"))).toEqual({
      periodStartYear: 2026,
      periodStartMonth: 12,
      periodEndYear: 2027,
      periodEndMonth: 5,
    });
  });
});
