# Módulos

A Central de Indicadores acompanha quatro indicadores oficiais do
Scorecard (RDO, IDP/Cronograma, RNC e Horas Extras — este último em
desenvolvimento), mais o 5S (aba própria, fora do cálculo do Scorecard) e
uma área administrativa transversal.

Cada indicador com operação plena (RDO, IDP, RNC) segue o mesmo padrão de
tela: uma sub-aba **Painel** (somente leitura, mostra a publicação
vigente) e uma sub-aba **Administração** (dados ao vivo — importação,
configuração de meta, publicação), alternadas pelo switcher no canto
superior direito da barra de abas.

## RDO — Aprovação de relatórios

Calcula a taxa de aprovação dos Relatórios Diários de Obra por unidade e
mês, a partir de planilhas Excel/CSV importadas. Cada linha é identificada
por relatório + data + empresa + grupo + disciplina (um mesmo relatório
pode ter várias linhas, uma por grupo/disciplina). O status de cada linha
pode ser editado manualmente na Administração (Aprovado / Revisar
Relatório / Preenchendo Relatório).

- meta padrão: **80%** de aprovação;
- peso no Scorecard: **35%**.

## IDP — Aderência ao cronograma

Consolida a aderência ao cronograma físico de obra por disciplina, unidade
e mês, a partir de PDFs de RSO (Relatório de Serviço/Obra) importados e
lidos no navegador. Compara linha de base (planejado) com execução real.

- meta padrão: **90%** de aderência;
- peso no Scorecard: **40%** (o de maior peso).

## RNC — Não conformidades

Acompanha o prazo médio de tratativa das Não Conformidades por unidade,
identificando os principais ofensores. Duas definições de "resolvida"
convivem no cálculo (data de solução informada vs. tratativa concluída) —
os detalhes de arredondamento e critério vivem no código do módulo
(`backend/app/modules/rnc/`).

- meta padrão: **15 dias** (quanto menor, melhor);
- peso no Scorecard: **15%**.

## Horas Extras Pagas (em desenvolvimento)

Quarto indicador oficial do Scorecard, com peso de **10%** já reservado,
mas ainda sem fórmula, fonte de dados ou regra de comparação definidas.
Aba própria em `/dashboard/horas-extras` (entre RNC e 5S na navegação),
mostrando só um estado informativo — sem formulário, importador, gráfico
ou chamada de API. Nunca pontua, nunca aparece como "fora da meta" ou "sem
dados"; o status é sempre "Em desenvolvimento — não contabilizado". Ver
`docs/scorecard.md` para a separação entre peso oficial e contabilizável.

## 5S — Programa 5S

Não integra mais o Scorecard (alinhamento 2026-alinhamento-v2). A aba
`/dashboard/cinco-s` continua na navegação, mas mostra só "Em breve" — sem
painel publicado, sem administração, sem chamada de API. Os dados
históricos e a API do módulo (`backend/app/modules/cinco_s/`) permanecem
intactos; só a UI dedicada e a participação no cálculo foram removidas.

## Scorecard e Painel Geral

Consolida os quatro indicadores oficiais (três ativos + Horas Extras
reservado) em um único painel por ciclo semestral. Não tem importação nem
lançamento próprio — lê exclusivamente as publicações ativas dos outros
módulos (ao vivo) ou snapshots salvos manualmente como respaldo histórico.
Ver `docs/scorecard.md` para as regras completas de pontuação.

## Justificativas

Cada indicador permite registrar uma justificativa textual por competência
(mês/ano), com uma sugestão gerada automaticamente a partir dos próprios
dados do módulo (recalculada sob demanda, não um texto fixo). Útil para
documentar por que uma meta não foi atingida ou por que um período ficou
sem publicação.

## Administração

Área transversal, disponível para os perfis `ANALYST` e `ADMIN`, reunindo:

- **Importações** — histórico de jobs, lotes processados e registros
  rejeitados por módulo;
- **Usuários** — cadastro, perfil de acesso e ativação (`ADMIN`);
- **Auditoria** — trilha de ações administrativas (`ADMIN`);
- **Configurações** — metas, listas de unidades excluídas e demais
  parâmetros por módulo, persistidos como configuração de aplicação (não
  hardcoded).

Todo painel administrativo de indicador trava o período de trabalho em um
seletor de Ano + Semestre. A exclusão de registros administrativos segue
sempre o mesmo padrão: primeiro uma contagem do que será afetado, depois a
exclusão em si (por período ou base inteira) — nunca remove a publicação
vigente, apenas os dados administrativos de origem.
