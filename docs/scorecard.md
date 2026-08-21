# Scorecard

O Scorecard consolida os cinco indicadores operacionais em uma única
pontuação por ciclo semestral. Não tem importação nem lançamento próprio —
lê exclusivamente as publicações dos outros módulos.

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

## Pontuação

```text
pontuação máxima do ciclo   = 11.582 pontos
pontuação máxima mensal     = 11.582 / 6 = 1.930,333333 pontos
pontos possíveis do indicador (por mês) = pontuação mensal × peso
pontos realizados                        = meta cumprida ? pontos possíveis : 0
```

| Indicador | Peso | Meta | Pontos possíveis/mês |
|---|---:|---:|---:|
| Aprovação RDO | 25,00% | ≥ 80% | 482,583333 |
| Aderência ao Cronograma (IDP) | 35,00% | ≥ 90% | 675,616667 |
| RNC | 10,00% | ≤ 15 dias | 193,033333 |
| 5S | 10,00% | ≥ 90% | 193,033333 |
| Taxa de Acidentes | 20,00% | ≤ 7,5 | 386,066667 |
| **Total mensal** | **100,00%** | — | **1.930,333333** |

Regras:

- **binário por indicador e por mês** — meta cumprida recebe a parcela
  inteira daquele mês; caso contrário, zero. Não há pontuação parcial.
- indicadores "maior ou igual" atendem quando `resultado ≥ meta`;
  indicadores "menor ou igual" (RNC, Taxa de Acidentes) atendem quando
  `resultado ≤ meta`.
- **resultado ausente conta como zero ponto** (nunca é ignorado do total).
- a precisão decimal é mantida durante todo o cálculo; o arredondamento
  acontece só na exibição/exportação.
- a soma máxima do ciclo permanece **11.582 pontos**, mesmo que algum mês
  ainda não tenha dado disponível.

## Origem dos valores

O painel de Administração do Scorecard **não permite edição manual** —
nenhum valor é digitado diretamente ali. Cada valor exibido é sempre um
destes dois:

1. o valor **ao vivo** publicado pelo módulo de origem (RDO/IDP/RNC/5S/
   Taxa de Acidentes) para aquele mês; ou
2. o último **snapshot salvo** (via botão "Salvar snapshot", que grava o
   valor ao vivo do momento do clique — nunca um ajuste manual digitado).

O valor ao vivo sempre prevalece sobre o snapshot salvo quando os dois
existem para o mesmo indicador/mês; o snapshot só é usado como respaldo
quando não há valor ao vivo disponível (por exemplo, módulo sem
publicação ativa naquele momento). Essa regra vive em
`backend/app/modules/scorecard/service.py`.

O botão "Limpar histórico" (somente `ADMIN`) apaga os snapshots salvos do
ciclo selecionado — os dados publicados nos módulos de origem não são
afetados e continuam disponíveis na leitura ao vivo.

## Painel Geral

O Painel Geral usa exclusivamente snapshots/publicações ativas dos módulos
— nunca dados administrativos não publicados — e mantém a pontuação
prevista em 11.582 pontos para o ciclo completo, mesmo com meses ainda sem
publicação.
