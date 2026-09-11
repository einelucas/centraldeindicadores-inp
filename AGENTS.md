# Especificação obrigatória para adequações e migrações

Este arquivo deve ser lido integralmente antes de iniciar qualquer adequação, migração, criação de tela, alteração visual ou implementação funcional no projeto Nuxt.

## 1. Independência obrigatória do Nuxt

O projeto localizado em `frontend/` deve ser completamente independente do projeto Next legado.

- Não importar CSS, componentes, funções, tipos, rotas, APIs, assets processados ou configurações diretamente do projeto Next.
- Não criar aliases, caminhos relativos, proxies ou dependências de execução apontando para arquivos do Next.
- Todo código necessário ao Nuxt deve existir dentro da arquitetura do próprio Nuxt ou em pacotes compartilhados explicitamente independentes do Next.
- Todo CSS usado pelo Nuxt deve estar em `frontend/assets/css/vue.css`, em estilos locais de componentes Vue ou na configuração Tailwind do Nuxt.
- As rotas de interface devem ser rotas do Nuxt.
- A comunicação de dados deve utilizar exclusivamente os serviços e contratos próprios do Nuxt com o backend FastAPI.
- Uma migração não está concluída enquanto existir dependência de execução do Nuxt em relação ao Next.

O projeto Next pode ser consultado somente como referência visual e funcional. Consultar não significa importar ou compartilhar arquivos em tempo de execução.

## 2. Fontes de verdade do design

As fontes de verdade devem ser aplicadas nesta ordem:

1. O esqueleto global já consolidado no Nuxt: cabeçalho, navegação, largura dos containers, títulos de página, seletores, barras de ações, espaçamentos, alturas, estados de carregamento, estados vazios e estrutura dos painéis publicados.
2. O módulo RDO do Nuxt, que é a referência de implementação completa para componentes, cards, upload, feedback de processamento e integração entre Painel e Administração.
3. O projeto Next, usado como fonte de verdade visual e funcional para o conteúdo específico de cada módulo, especialmente o painel administrativo.

Quando houver diferença entre o esqueleto do Next e o esqueleto consolidado do Nuxt, prevalece o esqueleto do Nuxt.

## 3. Reutilização de componentes e cards

- Não recriar interfaces a partir de fotografias ou capturas de tela.
- Imagens podem ser usadas apenas para conferência visual, nunca como especificação estrutural primária.
- Antes de criar um componente, procurar componentes, variantes, tokens e padrões existentes no Nuxt.
- Reutilizar os componentes e cards já empregados no RDO sempre que representarem o mesmo padrão visual ou funcional.
- Criar um novo componente Vue apenas quando não houver componente compatível ou quando a extração eliminar duplicação real.
- Um componente novo deve pertencer à arquitetura do Nuxt e não pode depender do projeto Next.
- Os cards são os únicos elementos visuais do Next que podem ser portados. Mesmo nesse caso, devem ser convertidos em componentes Vue independentes ou em variantes dos componentes existentes; nunca devem ser importados diretamente do Next.
- Cards equivalentes entre módulos devem compartilhar o mesmo componente e variar apenas por propriedades, dados, ícones e estados previstos pelo componente.

## 4. Painéis publicados

- Todas as abas publicadas devem seguir o mesmo esqueleto fixo do Nuxt.
- O cabeçalho deve reutilizar o seletor de período, os estilos, as dimensões, os espaçamentos e os estados definidos no Nuxt.
- A barra do painel publicado deve exibir somente a ação de exportar PDF, salvo nova especificação expressa do responsável pelo projeto.
- Não exibir botões de atualização manual ou exportação Excel no painel publicado.
- Após uma publicação bem-sucedida no painel administrativo, o painel publicado correspondente deve atualizar os dados automaticamente pelo mecanismo de eventos do Nuxt.
- Estados de carregamento, erro e ausência de publicação devem manter altura e espaçamento consistentes entre todos os módulos.

## 5. Painéis administrativos

- O painel administrativo de cada módulo no Nuxt deve reproduzir o painel administrativo correspondente do Next em conteúdo, hierarquia visual e comportamento.
- Todas as funções existentes no Next devem estar funcionais no Nuxt, incluindo ações, filtros, validações, configurações, publicação, exclusão, justificativas, exportações e demais fluxos aplicáveis ao módulo.
- Todas as tabelas relevantes devem ser migradas com suas colunas, dados, filtros, estados, paginação ou rolagem e ações aplicáveis.
- Não substituir uma função do Next por um placeholder, botão inativo ou dados simulados sem autorização expressa.
- A fidelidade ao Next não autoriza copiar dependências técnicas. A implementação deve usar componentes Vue, composables, serviços e contratos existentes no Nuxt/FastAPI.

## 6. Upload e processamento de arquivos

- Todo upload de arquivos nos painéis administrativos deve permitir selecionar arquivos e arrastar e soltar.
- O componente e o fluxo do RDO devem ser usados como referência principal.
- A área de upload deve apresentar estados visuais claros para repouso, arraste ativo, processamento, sucesso e erro.
- Durante o tratamento dos arquivos, deve existir animação ou indicador de progresso perceptível e os controles incompatíveis devem permanecer desabilitados.
- O feedback deve informar, quando disponível, arquivo em tratamento, quantidade processada, duplicidades ignoradas, erros e conclusão.
- O processamento deve utilizar o fluxo de importação e os endpoints do backend FastAPI, sem depender de rotas ou APIs do Next.

## 7. Fluxo obrigatório antes de implementar

Antes de alterar o código:

1. Ler este arquivo integralmente.
2. Identificar o esqueleto e os componentes equivalentes já existentes no Nuxt.
3. Inspecionar o módulo RDO quando a tarefa envolver cards, upload, processamento, publicação ou painel administrativo.
4. Consultar o Next somente para entender o design e as funções específicas que precisam ser reproduzidas.
5. Mapear as dependências necessárias para componentes, composables, tipos, rotas Nuxt e endpoints FastAPI.
6. Implementar sem criar dependência com o Next.

## 8. Critérios de conclusão

Uma adequação ou migração somente pode ser considerada concluída quando:

- respeita o esqueleto do Nuxt;
- reutiliza os componentes existentes sempre que aplicável;
- não foi recriada a partir de fotografia;
- não possui imports, estilos, aliases, rotas ou chamadas de API dependentes do Next;
- reproduz todas as funções e tabelas administrativas aplicáveis;
- possui upload por seleção e arrastar e soltar, com feedback animado de processamento, quando houver importação;
- atualiza automaticamente o painel publicado após a publicação administrativa;
- passa por typecheck, testes e build proporcionais à alteração;
- foi verificada quanto a regressões visuais e funcionais no módulo alterado.

Se uma solicitação futura entrar em conflito com este arquivo, a instrução mais recente e explícita do responsável pelo projeto prevalece. O conflito e a decisão adotada devem ser registrados na entrega.
