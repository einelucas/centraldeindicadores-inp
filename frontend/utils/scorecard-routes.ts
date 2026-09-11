/** Rota Nuxt do módulo de origem por chave de indicador do Scorecard.
 * Compartilhada entre o Painel Geral e a Administração do Scorecard — uma
 * célula mensal do Painel Executivo só vira link quando a chave do
 * indicador aparece aqui. */
export const SCORECARD_INDICATOR_ROUTES: Record<string, string> = {
  rdo: "/dashboard/rdo",
  cronograma: "/dashboard/idp",
  rnc: "/dashboard/rnc",
  horas_extras: "/dashboard/horas-extras",
};
