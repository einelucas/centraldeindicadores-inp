# Arquitetura

## Visão geral

A Central de Indicadores é composta por dois serviços independentes que
conversam por HTTP/JSON, mais um banco PostgreSQL:

```text
frontend/ (Nuxt 4 + Vue 3)
        │
        │  HTTP / JSON  (NUXT_PUBLIC_API_BASE_URL)
        ▼
backend/ (FastAPI + Pydantic)
        │
        │  SQLAlchemy assíncrono (asyncpg)
        ▼
PostgreSQL
```

- **`frontend/`** — aplicação Nuxt 4 (Vue 3 + TypeScript). Não acessa o
  banco nem contém regra de negócio: todo cálculo, validação e persistência
  vêm da API.
- **`backend/`** — API FastAPI. Concentra autenticação, permissões,
  validação, cálculo dos indicadores e persistência.
- **PostgreSQL** — único banco de dados, acessado apenas pelo backend.

## Camadas do backend

Cada módulo de indicador (`backend/app/modules/<modulo>/`) segue o mesmo
padrão de arquivos:

```text
app/modules/<modulo>/
├── types.py          # constantes e tipos do domínio (metas, colunas aceitas)
├── schemas.py         # contratos Pydantic de entrada/saída
├── keys.py            # business key + content hash do módulo
├── calculations.py    # cálculo do indicador (função pura, testável)
├── repository.py       # acesso a dados (SQLAlchemy)
├── service.py           # orquestração: valida, persiste, recalcula, publica
├── publications.py      # payload de publicação (o que vira snapshot)
└── router.py            # endpoints FastAPI — nunca contém regra de negócio
```

Esse isolamento permite alterar um módulo sem afetar os demais, e mantém o
cálculo (`calculations.py`) testável isoladamente, sem banco nem HTTP.

## Código compartilhado do backend

`app/shared/` reúne utilitários usados por todos os módulos, sem
dependência de nenhum módulo específico:

- `period` / `period_params` — resolução de período operacional (semestre,
  competências) e parsing dos parâmetros de query;
- `hashing` — geração de business key e content hash;
- `normalization`, `dates`, `units` — normalização de texto, datas e
  unidades vindas de planilhas;
- `batching` — processamento de lotes de importação;
- `incremental_upsert` — motor genérico de inserir/ignorar/atualizar por
  business key, reaproveitado por todos os módulos com importação;
- `publication_cycle` — resolução do ciclo (semestre) e do snapshot vigente
  para um indicador;
- `pagination`, `audit`, `schema` (modelo Pydantic com contrato camelCase).

`app/core/` reúne infraestrutura transversal: configuração (`config.py`,
via variáveis de ambiente), conexão com o banco (`database.py`),
autenticação (`auth.py`), matriz de permissões (`permissions.py`),
tratamento de erros HTTP (`errors.py`) e logging estruturado
(`logging.py`).

## Fluxo de um indicador

```text
Arquivo (Excel/CSV) ou lançamento manual
        │  parsing no navegador (frontend)
        ▼
POST /api/v1/importacoes/iniciar → .../lotes → .../finalizar
        │  validação + business key/content hash + upsert incremental (backend)
        ▼
Persistência no PostgreSQL
        │  recálculo do módulo
        ▼
Cálculo administrativo disponível em GET /api/v1/<modulo>
        │  publicação
        ▼
POST /api/v1/publicacoes/<modulo> → snapshot versionado (IndicatorPublication)
        │
        ▼
GET /api/v1/publicacoes/<modulo> → painel de leitura do indicador
        │
        ▼
GET /api/v1/dashboard e GET /api/v1/scorecard → Painel Geral e Scorecard
```

Os painéis de leitura (a aba "Painel" de cada indicador, o Painel Geral e o
Scorecard) sempre leem **publicações/snapshots**, nunca os dados
administrativos "ao vivo" diretamente — uma alteração feita na
Administração só aparece no painel depois de uma nova publicação. A
exceção é a própria Administração, que sempre trabalha com o dado vivo
(ver `docs/modulos.md`).

## Frontend

O `frontend/` organiza-se por convenção do Nuxt:

```text
frontend/
├── pages/              # rotas (login, dashboard/<modulo>, administração)
├── layouts/             # shell autenticado (cabeçalho + abas por ícone)
├── components/
│   ├── layout/           # AppHeader, TabsNav, ModuleWorkspace (switcher Painel/Administração)
│   ├── indicators/        # PublishedPanel, IndicatorAdmin (genéricos, parametrizados por módulo)
│   ├── charts/            # gráficos SVG (linha e barra)
│   ├── admin/              # usuários, configurações, auditoria, histórico de importações
│   └── ui/                  # modal, cartão de métrica
├── composables/          # useApi (cliente HTTP), useAuth, useImports, useExport
├── stores/                # Pinia — estado de autenticação
├── middleware/            # guarda de rota (autenticado / admin)
└── types/                 # contratos TypeScript espelhando as respostas da API
```

`PublishedPanel` e `IndicatorAdmin` são componentes genéricos que recebem o
nome do módulo como prop e adaptam métricas, gráficos e tabelas — RDO, IDP,
RNC, 5S e Taxa de Acidentes reaproveitam os mesmos dois componentes em vez
de ter uma tela própria cada um.

## Importação de planilhas

A leitura de Excel/CSV/PDF acontece **no navegador** — o parsing nunca
acontece no backend. O frontend lê o arquivo, normaliza os campos e envia
apenas o JSON já estruturado para a API, que então gera business key e
content hash **no servidor** (fonte de verdade) e aplica o motor de
importação incremental. Arquivos originais não são persistidos em nenhum
momento. Ver `docs/importacao.md`.

## Autenticação e autorização

Keycloak (OIDC) é o provedor de identidade; um bypass de desenvolvimento
permite testar sem Keycloak real. Perfis `VIEWER`/`ANALYST`/`ADMIN` são
sempre verificados no servidor. Ver `docs/autenticacao.md`.

## Testes

- **Backend** — `pytest`: unitários (cálculo, hashing, normalização, sem
  banco), integração (fluxo HTTP completo contra um PostgreSQL real) e
  contrato (`tests/contract/`, compara as funções compartilhadas —
  hashing, normalização, datas, período — contra vetores fixos em
  `tests/fixtures/contract_vectors.json`, com tolerância `1e-9`).
- **Frontend** — `vitest`: utilitários puros (período, formatação).
