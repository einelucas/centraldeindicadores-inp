# Decisões técnicas e regras de comportamento

Este documento registra decisões de implementação que afetam comportamento, testes, persistência ou cálculo da Central de Indicadores.

O objetivo é evitar que detalhes importantes sejam alterados sem compreender seus impactos. As regras abaixo descrevem o sistema atual e devem ser lidas em conjunto com o código e os testes da branch `main`.

> O nome físico deste arquivo é mantido por compatibilidade com referências internas existentes no código. O conteúdo representa decisões técnicas atuais da aplicação.

## 1. Banco dedicado para testes

A suíte de integração executa limpeza de tabelas entre testes. Por isso, deve usar um PostgreSQL dedicado exclusivamente a testes.

Regras permanentes:

- `backend/.env` e `backend/.env.test` não devem apontar para o mesmo banco;
- o banco de teste deve ser descartável;
- a configuração de testes deve ser carregada antes de inicializar conexões da aplicação;
- proteções de ambiente devem impedir `TRUNCATE` em banco que não tenha sido explicitamente configurado como teste.

Essa regra existe para proteger dados utilizados durante desenvolvimento e validação manual.

## 2. PostgreSQL nos testes de integração

Os testes de integração usam PostgreSQL real porque o sistema depende de comportamentos específicos do banco, incluindo:

- constraints;
- JSON;
- índices únicos/parciais;
- `TRUNCATE ... CASCADE`;
- semântica de transações e conflitos.

SQLite não é substituto aceitável para essa camada de testes.

## 3. Event loop do pytest-asyncio

`asyncio_default_fixture_loop_scope = "function"`.

Cada teste recebe seu próprio event loop para evitar compartilhamento indevido de conexões `asyncpg` entre loops diferentes.

Alterar esse escopo exige validar novamente a interação entre pytest-asyncio, SQLAlchemy async e o pool configurado pelo backend.

## 4. IDP — baseline igual a zero

`calculate_idp_adherence` retorna `0.0` quando o valor previsto é zero ou não finito.

Isso mantém unidades/disciplinas sem baseline válido dentro da consolidação como aderência zero, em vez de removê-las silenciosamente da média.

Teste associado: `backend/tests/unit/test_idp_calculations.py`.

## 5. IDP — período ausente

Quando a leitura do IDP ocorre sem período explícito, o backend resolve a competência mais recente disponível. Se não houver registros, utiliza a competência corrente do servidor como fallback de apresentação.

Chamadas dos painéis devem preferir período operacional explícito sempre que o contexto já o conhece.

## 6. IDP — hashing de estruturas aninhadas

Campos estruturados do RSO, como listas e objetos, são serializados de forma determinística antes de entrar no content hash.

A serialização deve:

- ser estável;
- preservar mudanças de conteúdo;
- evitar que duas estruturas diferentes produzam a mesma representação trivial.

A implementação usa JSON determinístico para esses campos.

## 7. IDP — registros persistidos inválidos

Ao reconstruir registros de RSO a partir do banco, uma linha inconsistente deve ser tratada de forma controlada e contabilizada como inválida, evitando que um único registro corrompido derrube toda a rota.

O comportamento precisa continuar observável por logs/contagem para permitir correção da base.

## 8. IDP — disciplinas excluídas

A configuração `idp.excludedDisciplines` aceita os formatos suportados pela camada de configuração atual, incluindo representação textual e lista normalizada.

A normalização deve produzir uma coleção consistente antes do cálculo.

## 9. RNC — data de solução inválida

`dataCriacao` inválida impede que o registro seja usado corretamente e deve ser tratada pela validação do módulo.

Já uma `dataSolucao` ausente ou não utilizável pode representar uma não conformidade ainda sem solução e, conforme a implementação atual, é tratada como valor nulo quando o restante do registro é válido.

## 10. Publicações e dados administrativos

Dados administrativos e publicações são conceitos separados.

- importação/edição altera a base administrativa;
- cálculo administrativo reflete essa base;
- publicação cria o snapshot de leitura;
- painéis publicados não devem trocar automaticamente para dados administrativos não publicados.

## 11. Scorecard

A fonte de verdade dos indicadores oficiais está em `backend/app/modules/scorecard/types.py`.

Regras atuais:

- RDO: 35%;
- IDP/Cronograma: 40%;
- RNC: 15%;
- Horas Extras Pagas: 10% reservado;
- 5S: fora do Scorecard.

O peso reservado não deve ser redistribuído entre os demais indicadores.

## 12. Atualização deste documento

Uma decisão deve ser registrada aqui quando:

- altera comportamento observável de cálculo;
- evita risco relevante de perda de dados;
- muda uma convenção transversal de persistência/teste;
- resolve uma ambiguidade de domínio que não é óbvia pelo tipo ou pelo endpoint.

Não usar este arquivo como histórico de tecnologias anteriores; documente sempre a regra vigente da aplicação.
