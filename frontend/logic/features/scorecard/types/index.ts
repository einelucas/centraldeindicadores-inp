/**
 * Constantes do ciclo do Scorecard usadas pelo Painel Geral (Vue).
 *
 * Fonte de verdade: `backend/app/modules/scorecard/types.py`. Este arquivo
 * expõe apenas os dois números fixos do ciclo (que não mudam com o
 * realinhamento de pesos entre indicadores) — nunca reintroduzir aqui pesos,
 * metas ou a lista de indicadores: eles vivem só no backend.
 */

/** Pontuação máxima do ciclo de seis meses. */
export const SCORECARD_MAX_POINTS = 11_582;

/** Quantidade de meses de um ciclo padrão. */
export const SCORECARD_PERIOD_LENGTH = 6;

/** Pontuação máxima disponível em cada mês do ciclo. */
export const SCORECARD_MONTHLY_POOL = SCORECARD_MAX_POINTS / SCORECARD_PERIOD_LENGTH;
