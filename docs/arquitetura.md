# Arquitetura

## Visão geral

A Central de Indicadores é uma aplicação web em três camadas:

```text
frontend/ — Nuxt 4 + Vue 3 + TypeScript
        │
        │ HTTP/JSON
        ▼
backend/ — FastAPI + Pydantic
        │
        │ SQLAlchemy assíncrono
        ▼
PostgreSQL
```

- **Frontend**: interface, navegação, filtros, upload, visualização e exportação.
- **Backend**: autenticação, autorização, validação, regras de negócio, cálculos, publicações e persistência.
- **PostgreSQL**: fonte persistente de dados administrativos, resultados, publicações, configurações e auditoria.

O frontend não acessa o banco diretamente. Toda regra de negócio relevante deve ser validada no backend.

## Backend

O backend está em `backend/app/` e expõe a API sob `/api/v1`.

```text
backend/app/
├── main.py
├── api/v1/
├── core/
├── models/
├── modules/
└── shared/
```

### `core/`

Infraestrutura transversal:

- configuração por variáveis de ambiente;
- conexão assíncrona com PostgreSQL;
- autenticação OIDC/Keycloak;
- matriz de permissões;
- tratamento uniforme de erros;
- logging estruturado e correlation id.

### `modules/`

Cada domínio possui seu próprio pacote. Os módulos principais atuais são:

- `rdo`;
- `idp`;
- `rnc`;
- `cinco_s`;
- `scorecard`;
- `dashboard`;
- `imports`;
- `indicators`;
- `justifications`;
- `users`;
- `settings`;
- `audit`.

Módulos de indicador separam, conforme a necessidade, tipos, schemas, cálculo, repositório, serviços, publicação e rotas. A regra de negócio não deve ficar diretamente no router.

### `shared/`

Utilitários reaproveitados entre módulos, incluindo período operacional, normalização, datas, unidades, hashing, paginação, batching e persistência incremental.

## Frontend

O frontend está em `frontend/` e segue as convenções do Nuxt.

```text
frontend/
├── app.vue
├── pages/
├── layouts/
├── components/
│   ├── admin/
│   ├── charts/
│   ├── dashboard/
│   ├── filters/
│   ├── indicators/
│   ├── layout/
│   ├── scorecard/
│   └── ui/
├── composables/
├── logic/
├── middleware/
├── services/
├── stores/
├── types/
├── utils/
└── assets/
```

### Páginas e workspaces

Os módulos operacionais usam `ModuleWorkspace`, separando:

- **Painel**: leitura da publicação vigente;
- **Administração**: importação, ajustes, cálculo, publicação e ações administrativas disponíveis ao perfil do usuário.

RDO, IDP e RNC possuem operação completa. Horas Extras possui interface própria em preparação para a integração de dados. 5S mantém uma página própria com estado informativo.

### Componentes compartilhados

A aplicação reutiliza seletores de período/unidade, cards, estados vazios, modais e gráficos SVG. Componentes como `LineChart`, `BarChart`, `DonutChart` e `UnitProgressBars` são compartilhados entre os painéis.

## Fluxo de dados

O fluxo padrão dos módulos operacionais é:

```text
arquivo / entrada administrativa
        ↓
normalização e validação
        ↓
deduplicação + persistência incremental
        ↓
recálculo do módulo
        ↓
resultado administrativo
        ↓
publicação versionada
        ↓
painel publicado
        ↓
Painel Geral / Scorecard
```

A publicação cria uma visão estável para consulta. Alterações feitas na Administração não substituem automaticamente a publicação vigente até que uma nova publicação seja realizada.

## Publicações

`IndicatorPublication` representa os snapshots versionados exibidos nos painéis. O backend mantém a regra de qual publicação está ativa para cada módulo/ciclo.

O Painel Geral e o Scorecard usam os resultados publicados dos módulos ativos, com snapshots próprios do Scorecard como respaldo histórico quando aplicável.

## Importação

A aplicação possui infraestrutura genérica de importação incremental. RDO e RNC aceitam upload direto de arquivos para o FastAPI, que faz parsing, validação, deduplicação e bulk upsert. IDP e 5S utilizam os fluxos atualmente implementados para seus respectivos formatos.

Business key e content hash são gerados no backend e definem se um registro é inserido, atualizado ou ignorado.

Veja [`importacao.md`](importacao.md).

## Autenticação e autorização

A autenticação corporativa usa Keycloak/OIDC. O backend valida o token e resolve o usuário local; permissões são derivadas do perfil persistido no banco.

Perfis atuais:

- `VIEWER`;
- `ANALYST`;
- `ADMIN`.

Veja [`autenticacao.md`](autenticacao.md).

## Banco de dados

O backend usa SQLAlchemy 2 assíncrono com PostgreSQL. A evolução de schema é controlada pelo Alembic. O frontend não possui conexão direta com o banco.

Veja [`banco-de-dados.md`](banco-de-dados.md).

## Testes e qualidade

Backend:

- `pytest` / `pytest-asyncio`;
- `ruff`;
- `mypy`;
- testes unitários, integração e contrato.

Frontend:

- `vitest`;
- `eslint`;
- `nuxt typecheck`;
- `nuxt build`.

As alterações devem preservar os contratos entre frontend e backend e evitar duplicação de regra de negócio entre as camadas.
