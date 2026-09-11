/**
 * Cadastro canônico das unidades operacionais, compartilhado por todos os
 * módulos (RDO, RNC, 5S, IDP). Uma mesma unidade pode aparecer nos
 * documentos de origem sob mais de uma sigla — por isso `UNIT_CODE_ALIASES`
 * resolve siglas alternativas para o código canônico antes de qualquer
 * agregação/exibição, garantindo que a unidade seja sempre consolidada sob
 * um único nome. Siglas não cadastradas aqui NUNCA são inventadas —
 * permanecem como texto livre, estabilizado em caixa alta.
 */

import { collapseSpaces, normalizeForMatch } from "~/logic/lib/normalization";

export interface UnitDefinition {
  code: string;
  name: string;
}

export const UNITS: readonly UnitDefinition[] = [
  { code: "LEM", name: "LUIS EDUARDO MAGALHÃES" },
  { code: "MTU", name: "NOVA MUTUM" },
  { code: "RVD", name: "RIO VERDE" },
  { code: "BLS", name: "BALSAS" },
  { code: "SNP", name: "SINOP" },
  { code: "DRD", name: "DOURADOS" },
  { code: "RDN", name: "RONDONÓPOLIS" },
  { code: "SDL", name: "SIDROLÂNDIA" },
  { code: "LRL", name: "LAUREL" },
] as const;

/**
 * Siglas alternativas encontradas nos arquivos de origem que representam a
 * MESMA unidade que um código já cadastrado acima — nunca criam uma unidade
 * nova, só resolvem para o código canônico (ex.: NMT e MTU são a mesma
 * unidade, NOVA MUTUM, e devem ser consolidadas sob um único nome em todos
 * os filtros, gráficos e totalizações).
 */
export const UNIT_CODE_ALIASES: Readonly<Record<string, string>> = {
  NMT: "MTU",
  // "SDR" era o código usado para esta unidade antes da correção para o
  // código oficial "SDL" — mantido como alias para não deixar de reconhecer
  // arquivos de origem antigos que ainda usem a sigla anterior.
  SDR: "SDL",
};

const UNIT_BY_CODE = new Map<string, UnitDefinition>(UNITS.map((unit) => [unit.code, unit]));
const UNIT_ORDER = new Map<string, number>(UNITS.map((unit, index) => [unit.code, index]));
const CODE_LOOKUP = new Map<string, string>([
  ...UNITS.map((unit): [string, string] => [unit.code, unit.code]),
  ...Object.entries(UNIT_CODE_ALIASES),
]);

/**
 * Converte sigla (inclusive alias), nome completo (em qualquer
 * caixa/acentuação) ou rótulo combinado para a sigla oficial. Unidades fora
 * do cadastro continuam disponíveis, estabilizadas em caixa alta — nunca são
 * presumidas como uma unidade cadastrada.
 */
export function normalizeUnitCode(value: unknown): string {
  const raw = collapseSpaces(String(value ?? ""));
  if (!raw) return "";

  const normalized = normalizeForMatch(raw);

  const direct = CODE_LOOKUP.get(normalized);
  if (direct) return direct;

  for (const unit of UNITS) {
    const normalizedName = normalizeForMatch(unit.name);
    if (
      normalized === normalizedName ||
      normalized === `${unit.code} ${normalizedName}` ||
      normalized === `${normalizedName} ${unit.code}` ||
      normalized.includes(normalizedName)
    ) {
      return unit.code;
    }
  }

  for (const token of normalized.split(" ")) {
    const aliased = CODE_LOOKUP.get(token);
    if (aliased) return aliased;
  }

  return raw.toUpperCase();
}

/** Exibe o nome completo por extenso da unidade — nunca a sigla nem
 * prefixos soltos. Este é o único texto que deve chegar à interface. */
export function formatUnitLabel(value: unknown): string {
  const code = normalizeUnitCode(value);
  return UNIT_BY_CODE.get(code)?.name ?? code;
}

/** Mantém as unidades oficiais na ordem operacional cadastrada. */
export function compareUnits(a: unknown, b: unknown): number {
  const codeA = normalizeUnitCode(a);
  const codeB = normalizeUnitCode(b);
  const orderA = UNIT_ORDER.get(codeA) ?? Number.MAX_SAFE_INTEGER;
  const orderB = UNIT_ORDER.get(codeB) ?? Number.MAX_SAFE_INTEGER;

  return orderA - orderB || formatUnitLabel(codeA).localeCompare(formatUnitLabel(codeB), "pt-BR");
}
