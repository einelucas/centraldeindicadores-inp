# Documentação técnica

A documentação da Central de Indicadores descreve a aplicação como ela existe hoje: frontend Nuxt/Vue, backend FastAPI e PostgreSQL.

| Documento | Conteúdo |
|---|---|
| [`arquitetura.md`](arquitetura.md) | Arquitetura do frontend, backend, banco e fluxo de publicação |
| [`modulos.md`](modulos.md) | Módulos existentes, finalidade, metas, pesos e estado funcional |
| [`scorecard.md`](scorecard.md) | Ciclo semestral, pesos, pontuação e origem dos resultados |
| [`importacao.md`](importacao.md) | Upload, normalização, deduplicação e persistência incremental |
| [`autenticacao.md`](autenticacao.md) | Keycloak/OIDC, sessão e matriz de permissões |
| [`banco-de-dados.md`](banco-de-dados.md) | Modelos principais, configurações e Alembic |
| [`api.md`](api.md) | Endpoints FastAPI por domínio |
| [`desenvolvimento.md`](desenvolvimento.md) | Ambiente local, convenções, testes e qualidade |

Guias por camada:

- [`frontend/README.md`](../frontend/README.md) — estrutura, componentes e convenções do Nuxt/Vue;
- [`backend/README.md`](../backend/README.md) — ambiente Python, FastAPI, testes e banco;
- [`README.md`](../README.md) — visão geral e instalação rápida.

## Fontes de verdade

Ao atualizar a documentação, considere nesta ordem:

1. código da branch `main`;
2. contratos expostos pela API FastAPI e tipos do frontend;
3. testes automatizados;
4. documentação deste diretório.

Documentos não devem descrever tecnologias, módulos, rotas ou fluxos que não existem na aplicação atual.
