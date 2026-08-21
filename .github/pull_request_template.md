## Descrição

<!-- O que esta mudança faz e por quê. -->

## Tipo de mudança

- [ ] Correção de bug
- [ ] Nova funcionalidade
- [ ] Refatoração (sem mudança de comportamento)
- [ ] Documentação
- [ ] Alteração de schema (Alembic)

## Módulo(s) afetado(s)

<!-- Ex.: RDO, importação incremental, autenticação, etc. -->

## Checklist

- [ ] Backend: `ruff check`, `mypy` e `pytest` passam localmente
- [ ] Frontend: `pnpm lint`, `pnpm typecheck`, `pnpm test` e `pnpm build` passam localmente
- [ ] Testes adicionados/atualizados para a mudança
- [ ] Se houve mudança de schema, a migration Alembic foi gerada e revisada
- [ ] Regras de negócio preservadas (business key / content hash quando aplicável)
- [ ] Sem segredos, credenciais ou dados sensíveis no código/commits

## Como testar

<!-- Passos para validar manualmente. -->
