# Módulos

A Central de Indicadores organiza os indicadores operacionais em módulos independentes, com backend FastAPI e interface Nuxt/Vue.

## Visão geral

| Módulo | Estado | Meta principal | Peso no Scorecard |
|---|---|---:|---:|
| RDO | Operacional | ≥ 80% de aprovação | 35% |
| IDP / Cronograma | Operacional | ≥ 90% de aderência | 40% |
| RNC | Operacional | ≤ 15 dias | 15% |
| Horas Extras Pagas | Interface preparada / regra parcial | ≤ 1% de referência | 10% reservado |
| 5S | Página informativa | — | Fora do Scorecard |
| Scorecard | Operacional | Consolidação semestral | — |
| Painel Geral | Operacional | Visão consolidada | — |

## RDO — Aprovação de Relatórios Diários de Obra

O módulo RDO acompanha a aprovação dos Relatórios Diários de Obra por unidade, mês e ciclo.

Principais recursos:

- importação de arquivos Excel/CSV;
- normalização e deduplicação no backend;
- atualização incremental por business key + content hash;
- cálculo de relatórios emitidos, aprovados, em revisão e em preenchimento;
- leitura mensal e por unidade;
- edição administrativa dos status suportados;
- publicação versionada;
- painel publicado com filtros de período e unidade;
- exportação em PDF;
- justificativas administrativas.

**Meta padrão:** 80% de aprovação.  
**Peso:** 35%.

## IDP — Aderência do Cronograma

O IDP consolida a aderência da execução física ao cronograma por RSO, disciplina, unidade e período.

Principais recursos:

- importação e tratamento dos dados de RSO;
- cálculo da aderência planejado × realizado;
- consolidação por disciplina, unidade e competência;
- filtros por período e unidade;
- publicação versionada;
- visualização da aderência geral e detalhada;
- justificativas administrativas.

**Meta padrão:** 90% de aderência.  
**Peso:** 40%.

## RNC — Não Conformidades

O módulo RNC acompanha o tempo de tratativa das não conformidades e sua distribuição por unidade e origem.

Principais recursos:

- importação de planilhas;
- cálculo do prazo médio de resolução;
- consolidação de registros criados e tratados;
- identificação de ofensores/origens;
- leitura mensal e por unidade;
- publicação versionada;
- painel com comparação de resultado, meta e aderência de tratativa;
- justificativas administrativas.

**Meta padrão:** até 15 dias.  
**Peso:** 15%.

A direção desse indicador é **menor é melhor**.

## Horas Extras Pagas

Módulo de RH destinado ao acompanhamento do percentual de horas extras pagas por unidade e período.

A interface já está estruturada no mesmo padrão visual dos demais indicadores e possui as seguintes regras conhecidas:

- unidade esperada: `%`;
- direção: **menor é melhor**;
- meta de referência: **≤ 1%**;
- faixa de desempenho de 80%: **> 1% e ≤ 2%**;
- peso oficial: **10%**.

A fonte de dados, a fórmula operacional completa e as demais faixas de pontuação ainda não estão definidas. Por isso, o peso permanece **reservado** e não participa da pontuação realizada do Scorecard.

A aba possui Painel e Administração, mas a importação permanece bloqueada até existir um layout oficial de dados.

## 5S

A aplicação mantém uma página dedicada ao 5S, atualmente em estado informativo **Em breve**.

O 5S não participa do Scorecard atual.

## Scorecard

O Scorecard consolida o desempenho do ciclo semestral e calcula a pontuação dos indicadores oficiais ativos.

Ele não possui uma base de dados independente de resultados de negócio: consome as publicações dos módulos de origem e mantém snapshots próprios como respaldo histórico.

Veja [`scorecard.md`](scorecard.md).

## Painel Geral

O Painel Geral apresenta uma visão consolidada do ciclo selecionado, incluindo:

- resultado dos indicadores ativos;
- pontuação prevista;
- pontuação contabilizável;
- pontos reservados;
- cobertura do Scorecard;
- leitura por unidade e período quando disponível.

A fonte é sempre a publicação vigente dos módulos, não os dados administrativos ainda não publicados.

## Administração

A área administrativa reúne recursos transversais da aplicação:

- **Importações** — histórico e erros de processamento;
- **Usuários** — perfis, ativação e gerenciamento de acesso;
- **Configurações** — metas e parâmetros persistidos;
- **Auditoria** — trilha de ações administrativas;
- **Justificativas** — registro e sugestão para os módulos operacionais suportados.

As permissões variam conforme o perfil do usuário e são validadas no backend.

## Publicação

Nos módulos operacionais, o fluxo é:

```text
Dados administrativos
      ↓
Cálculo
      ↓
Publicação versionada
      ↓
Painel somente leitura
```

Uma alteração na Administração não substitui automaticamente a publicação vigente até que uma nova publicação seja realizada.
