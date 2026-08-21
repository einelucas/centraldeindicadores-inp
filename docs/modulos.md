# Módulos

A Central de Indicadores acompanha cinco indicadores operacionais, um
Scorecard que os consolida, e uma área administrativa transversal.

Cada indicador (RDO, IDP, RNC, 5S, Taxa de Acidentes) segue o mesmo padrão
de tela: uma sub-aba **Painel** (somente leitura, mostra a publicação
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
- peso no Scorecard: **25%**.

## IDP — Aderência ao cronograma

Consolida a aderência ao cronograma físico de obra por disciplina, unidade
e mês, a partir de PDFs de RSO (Relatório de Serviço/Obra) importados e
lidos no navegador. Compara linha de base (planejado) com execução real.

- meta padrão: **90%** de aderência;
- peso no Scorecard: **35%** (o de maior peso).

## RNC — Não conformidades

Acompanha o prazo médio de tratativa das Não Conformidades por unidade,
identificando os principais ofensores. Duas definições de "resolvida"
convivem no cálculo (data de solução informada vs. tratativa concluída) —
os detalhes de arredondamento e critério vivem no código do módulo
(`backend/app/modules/rnc/`).

- meta padrão: **15 dias** (quanto menor, melhor);
- peso no Scorecard: **10%**.

## 5S — Programa 5S

Calcula a aderência das auditorias 5S por unidade e área/mês, permitindo
excluir unidades específicas da consolidação (por exemplo, unidades sem o
programa implantado ainda).

- meta padrão: **90%** de aderência;
- peso no Scorecard: **10%**.

## Taxa de Acidentes

Único indicador sem importação de planilha: os lançamentos mensais (taxa
de frequência consolidada + acidentes CAF) e por unidade (CAF + SAF) são
cadastrados diretamente por formulário na Administração.

- meta padrão: **7,5** (quanto menor, melhor);
- peso no Scorecard: **20%**.

## Scorecard e Painel Geral

Consolida os cinco indicadores acima em um único painel por ciclo
semestral. Não tem importação nem lançamento próprio — lê exclusivamente
as publicações ativas dos outros módulos (ao vivo) ou snapshots salvos
manualmente como respaldo histórico. Ver `docs/scorecard.md` para as
regras completas de pontuação.

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
