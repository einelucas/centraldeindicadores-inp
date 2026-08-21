"""Scorecard 2026 — consolidação ponderada dos cinco indicadores do ciclo.

Lê exclusivamente `IndicatorPublication` (publicado pelos módulos de
origem: RDO, IDP, RNC, 5S, Taxa de Acidentes) e `ScorecardSnapshot`
(histórico congelado do próprio Scorecard). Não importa código de
`app.modules.rdo`/`idp`/`rnc`/`cinco_s`/`taxa_acidentes` — desacoplado por
desenho, conforme o plano de migração.
"""

from __future__ import annotations
