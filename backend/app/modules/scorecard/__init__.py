"""Scorecard — consolidação ponderada dos quatro indicadores oficiais do
ciclo (alinhamento 2026-alinhamento-v2): RDO, Cronograma (IDP) e RNC
(ativos, pontuam) mais Horas Extras (peso reservado, em desenvolvimento,
nunca pontua). 5S e Taxa de Acidentes não fazem mais parte do Scorecard.

Lê exclusivamente `IndicatorPublication` (publicado pelos módulos de
origem: RDO, IDP, RNC) e `ScorecardSnapshot` (histórico congelado do
próprio Scorecard). Não importa código de `app.modules.rdo`/`idp`/`rnc` —
desacoplado por desenho, conforme o plano de migração.
"""

from __future__ import annotations
