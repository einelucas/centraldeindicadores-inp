/** Rótulo de unidade do RNC — delega ao cadastro canônico compartilhado. */

export {
  UNITS as RNC_UNITS,
  normalizeUnitCode as normalizeRncUnitCode,
  formatUnitLabel as formatRncUnitLabel,
  compareUnits as compareRncUnits,
  type UnitDefinition as RncUnitDefinition,
} from "~/logic/lib/units";
