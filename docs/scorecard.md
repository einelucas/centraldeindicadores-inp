# Scorecard

O Scorecard consolida os quatro indicadores oficiais do ciclo semestral em
uma única pontuação — três ativos (contabilizáveis) e um em desenvolvimento
(peso reservado, ainda sem pontuação). Não tem importação nem lançamento
próprio — lê exclusivamente as publicações dos outros módulos.

Alinhamento vigente: **2026-alinhamento-v2**. 5S não integra mais o
Scorecard (aba mantida com "Em breve"); Taxa de Acidentes foi
descontinuada e removida completamente (código, API e schema do banco —
ver `docs/banco-de-dados.md`).

## Ciclo

O ciclo é sempre um semestre inteiro, escolhido por um seletor de Ano +
Semestre (o mesmo padrão usado nos demais painéis administrativos):

- **S2**: junho a novembro do ano selecionado;
- **S1**: dezembro do ano **anterior** a maio do ano selecionado (ex.: S1
  2027 = dez/2026 a mai/2027 — o "ano do período" é sempre o ano de
  término).

Não existe filtro livre de "de/até": o período usado tanto pela
Administração quanto pelo Painel Geral é sempre um desses dois semestres
inteiros (`backend/app/shared/period.py`).

## Pesos oficiais e contabilizáveis

```text
pontuação máxima do ciclo (oficial)     = 11.582 pontos
pontuação máxima mensal (oficial)       = 11.582 / 6 = 1.930,333333 pontos
pontos possíveis do indicador (por mês) = pontuação mensal × peso
pontos realizados                        = meta cumprida ? pontos possíveis : 0
```

| Indicador | Área | Peso oficial | Meta | Situação | Pontos/mês |
|---|---|---:|---:|---|---:|
| Aprovação RDO | Obras | 35,00% | ≥ 80% | Ativo | 675,616667 |
| Aderência ao Cronograma (IDP) | Planejamento | 40,00% | ≥ 90% | Ativo | 772,133333 |
| RNC | Conformidade de Obra | 15,00% | ≤ 15 dias | Ativo | 289,55 |
| Horas Extras Pagas | RH | 10,00% | referência 1 | **Em desenvolvimento** | 193,033333 (reservado) |
| **Total oficial** | | **100,00%** | — | | **1.930,333333** |

Enquanto Horas Extras estiver em desenvolvimento:

- **peso oficial total**: 100% (11.582 pontos no ciclo);
- **peso contabilizável**: 90% (10.423,80 pontos no ciclo / 1.737,30 por mês) —
  soma de RDO + Cronograma + RNC;
- **peso reservado**: 10% (1.158,20 pontos no ciclo / 193,033333 por mês) —
  Horas Extras, nunca pontua, nunca prejudica o resultado;
- o **percentual de atendimento dos indicadores ativos** usa como
  denominador só o pool contabilizável — com RDO, Cronograma e RNC todos na
  meta, o atendimento ativo é **100%**, não 90%;
- os pesos de RDO/Cronograma/RNC **não são redistribuídos** para
  "compensar" o peso reservado (nunca 38,89% / 44,44% / 16,67%).

Quando Horas Extras for ativado no futuro (fórmula, fonte e regra de
comparação definidas), o mesmo motor passa de 90% para 100% de peso
contabilizável automaticamente — sem redistribuição e sem reescrever o
cálculo. A fonte única de verdade de peso/meta/área/status de cada
indicador é `backend/app/modules/scorecard/types.py::SC_INDICATORS` — uma
união discriminada (`ActiveScorecardIndicator` vs.
`DevelopmentScorecardIndicator`) que impede, em tempo de compilação
(mypy), que um indicador em desenvolvimento seja enviado para a função de
pontuação (`calculations.score_indicator`).

Regras:

- **binário por indicador e por mês** — meta cumprida recebe a parcela
  inteira daquele mês; caso contrário, zero. Não há pontuação parcial.
- indicadores "maior ou igual" atendem quando `resultado ≥ meta`;
  indicadores "menor ou igual" (RNC) atendem quando `resultado ≤ meta`.
- **resultado ausente conta como zero ponto** (nunca é ignorado do total),
  exceto Horas Extras, que nunca é avaliado (não tem fórmula/fonte ainda) —
  seu status é sempre "Em desenvolvimento — não contabilizado", nunca "fora
  da meta" ou "sem dados".
- a precisão decimal é mantida durante todo o cálculo; o arredondamento
  acontece só na exibição/exportação.
- a soma máxima oficial do ciclo permanece **11.582 pontos**, mesmo que
  algum mês ainda não tenha dado disponível.

## Origem dos valores

O painel de Administração do Scorecard **não permite edição manual** —
nenhum valor é digitado diretamente ali. Cada valor exibido é sempre um
destes dois:

1. o valor **ao vivo** publicado pelo módulo de origem (RDO/IDP/RNC) para
   aquele mês; ou
2. o último **snapshot salvo** (via botão "Salvar snapshot", que grava o
   valor ao vivo do momento do clique — nunca um ajuste manual digitado).

Overrides manuais só são aceitos para os indicadores **ativos**
(RDO/Cronograma/RNC) — uma tentativa de enviar `horasExtras` (ou os
indicadores removidos `5s`/`taxaAcidentes`) em `overrides` é rejeitada com
422 pelo backend.

O valor ao vivo sempre prevalece sobre o snapshot salvo quando os dois
existem para o mesmo indicador/mês; o snapshot só é usado como respaldo
quando não há valor ao vivo disponível (por exemplo, módulo sem
publicação ativa naquele momento). Essa regra vive em
`backend/app/modules/scorecard/service.py`.

O botão "Limpar histórico" (somente `ADMIN`) apaga os snapshots salvos do
ciclo selecionado — os dados publicados nos módulos de origem não são
afetados e continuam disponíveis na leitura ao vivo.

Novos snapshots gravam a política vigente (`"policy": "2026-alinhamento-v2"`)
dentro de `raw`. Snapshots antigos sem esse campo continuam sendo lidos
normalmente. Chaves de indicadores antigos que não existem mais em
`SC_INDICATORS` (`5s`) são ignoradas silenciosamente pelo parser — nunca
causam erro. A chave `taxa_acidentes` é a única exceção: ela é removida
ativamente dos snapshots antigos pela rotina controlada
`backend/scripts/remove_taxa_acidentes_data.py --apply` (ver
`docs/banco-de-dados.md`), preservando os demais valores e recalculando o
`contentHash`.

## Painel Geral

O Painel Geral usa exclusivamente snapshots/publicações ativas dos módulos
— nunca dados administrativos não publicados — e mantém a pontuação
prevista oficial em 11.582 pontos para o ciclo completo, mesmo com meses
ainda sem publicação. Expõe os mesmos campos de pool contabilizável/
reservado do Scorecard (`pontuacaoPrevistaContabilizavel`,
`pontosReservados`, `atendimentoAtivosGeral`, `coberturaAtivaPct`).

## Horas Extras Pagas (em desenvolvimento)

Aba própria em `/dashboard/horas-extras`, entre RNC e 5S na navegação.
Mostra só um estado informativo — sem formulário, sem importador, sem
gráfico, sem dado simulado, sem chamada de API: o indicador já tem peso
oficial de 10% reservado no Scorecard, mas ainda não participa dos
cálculos. Fórmula, origem dos dados, unidade da meta e regra de comparação
ficam para quando a regra de negócio for definida — a meta de referência
`1` é só um metadado até lá.
