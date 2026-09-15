# Scorecard

O Scorecard consolida os indicadores oficiais da Central de Indicadores em ciclos semestrais.

Atualmente, três indicadores participam da pontuação realizada e um possui peso reservado:

| Indicador | Área | Peso oficial | Meta | Estado |
|---|---|---:|---:|---|
| Aprovação RDO | Obras | 35% | ≥ 80% | Ativo |
| Aderência ao Cronograma (IDP) | Planejamento | 40% | ≥ 90% | Ativo |
| RNC | Conformidade de Obra | 15% | ≤ 15 dias | Ativo |
| Horas Extras Pagas | RH | 10% | referência ≤ 1% | Em desenvolvimento |

O 5S não participa do Scorecard.

## Ciclos

O sistema trabalha com ciclos semestrais fixos:

- **S2**: junho a novembro do ano selecionado;
- **S1**: dezembro do ano anterior a maio do ano selecionado.

Exemplo: `S1 2027` representa dezembro de 2026 a maio de 2027.

## Pontuação

A pontuação máxima oficial do ciclo é **11.582 pontos**.

```text
pontuação máxima mensal = 11.582 / 6
pontos possíveis do indicador = pontuação mensal × peso oficial
```

Para os indicadores ativos, o cálculo mensal é binário:

```text
meta atingida     → recebe os pontos possíveis do mês
meta não atingida → recebe 0 ponto
```

Regras de direção:

- RDO: resultado `≥` meta;
- IDP: resultado `≥` meta;
- RNC: resultado `≤` meta.

A precisão decimal é preservada no cálculo e o arredondamento ocorre na apresentação.

## Peso contabilizável e peso reservado

Enquanto Horas Extras Pagas não possui fonte e fórmula operacional completas:

- peso oficial total: **100%**;
- peso contabilizável: **90%**;
- peso reservado: **10%**.

Os 10% reservados não geram pontos e também não reduzem artificialmente o percentual de atendimento dos indicadores ativos.

Os pesos de RDO, IDP e RNC não são redistribuídos.

## Horas Extras Pagas

O módulo já possui referências de negócio para apresentação:

- unidade: `%`;
- direção: menor é melhor;
- meta de referência: `≤ 1%`;
- faixa de 80%: `> 1% e ≤ 2%`;
- peso: `10%`.

A ativação da pontuação só deve ocorrer quando estiverem definidos e implementados:

1. fonte de dados oficial;
2. layout de importação;
3. fórmula final;
4. todas as faixas de pontuação;
5. validação do resultado com a área responsável.

Até lá, o indicador permanece fora do cálculo realizado.

## Fonte dos valores

O Scorecard não recebe digitação manual de resultado de negócio.

Os valores vêm das publicações dos módulos ativos. O backend pode utilizar snapshots do Scorecard como respaldo histórico quando não há um valor publicado disponível para a competência correspondente.

O valor publicado mais atual prevalece sobre o snapshot de respaldo.

## Snapshots

O Scorecard permite salvar snapshots mensais para preservar a visão consolidada de uma competência.

Os snapshots:

- não alteram os dados de origem;
- não substituem uma publicação mais atual;
- podem ser consultados no histórico do ciclo;
- podem ser limpos por usuários autorizados sem apagar publicações dos módulos.

## Painel Geral

O Painel Geral usa as mesmas fontes oficiais do Scorecard e apresenta a consolidação do ciclo selecionado.

Campos relevantes incluem:

- pontuação prevista oficial;
- pontuação contabilizável;
- pontos reservados;
- atendimento dos indicadores ativos;
- cobertura ativa do Scorecard.

## Fonte de verdade

Pesos, metas, direção e estado de participação dos indicadores do Scorecard vivem no backend, em `backend/app/modules/scorecard/types.py`.

A lógica de cálculo está em `backend/app/modules/scorecard/calculations.py` e a composição dos dados em `backend/app/modules/scorecard/service.py`.
