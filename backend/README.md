# Central de Indicadores — Backend

API FastAPI da Central de Indicadores: autenticação, permissões, cálculo
dos indicadores e persistência. O frontend (Nuxt, em `../frontend`) é um
cliente HTTP deste backend e não acessa o banco diretamente.

## Stack

- Python 3.12+
- FastAPI + Pydantic v2 + Pydantic Settings
- SQLAlchemy 2 assíncrono (`asyncpg`) + Alembic (migrations, via `psycopg` síncrono)
- PostgreSQL
- pytest + pytest-asyncio + httpx (`ASGITransport`, sem servidor real)
- Ruff (lint) + mypy (typecheck)

## Instalação

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\python.exe -m pip install -e ".[dev]"
# Linux/macOS:
.venv/bin/python -m pip install -e ".[dev]"

cp .env.example .env          # Linux/macOS/Git Bash
# Copy-Item .env.example .env   # PowerShell
```

Preencha `.env` com a `DATABASE_URL` do seu banco local/de testes.
**Nunca** aponte para o banco de produção — ver "Segurança do banco"
abaixo.

## Comandos

```bash
# Desenvolvimento (recarrega automaticamente)
.venv/Scripts/python.exe -m uvicorn app.main:app --reload

# Lint
.venv/Scripts/python.exe -m ruff check app tests scripts

# Typecheck
.venv/Scripts/python.exe -m mypy app

# Testes (requer PostgreSQL real acessível via DATABASE_URL — ver abaixo)
.venv/Scripts/python.exe -m pytest

# Testes com cobertura
.venv/Scripts/python.exe -m pytest --cov=app --cov-report=term-missing

# Exportar OpenAPI
.venv/Scripts/python.exe scripts/export_openapi.py

# Verificar drift de schema (modelos vs banco real)
.venv/Scripts/python.exe scripts/check_schema_drift.py

# Seed idempotente (configurações oficiais + usuário de teste)
.venv/Scripts/python.exe scripts/seed.py
```

A aplicação sobe em `http://localhost:8000`. Documentação interativa em
`/docs` (Swagger UI) e `/redoc`; schema bruto em `/openapi.json`.

## Segurança do banco

Regras aplicadas em código (`alembic/env.py`), não apenas em documentação:

- migrations do Alembic só executam quando `APP_ENV` é `test` ou
  `development` **e** `ALLOW_TEST_DB_MIGRATIONS=true`. Qualquer outra
  combinação interrompe a execução com `SystemExit`;
- antes de rodar, o `env.py` imprime host/porta/usuário/banco (nunca a
  senha) para conferência manual;
- se a URL de conexão contiver qualquer indício textual de produção
  (`prod`, `production`, `prd`), a migration é interrompida.

```bash
export APP_ENV=test
export ALLOW_TEST_DB_MIGRATIONS=true
export DATABASE_URL="postgresql://usuario:senha@host:porta/banco"

.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe scripts/seed.py
```

Para um banco que já tem os dados reais aplicados por outro processo, não
rode `alembic upgrade head` direto (recriaria tabelas existentes):

1. `scripts/check_schema_drift.py` confirma que o schema real bate com os
   modelos SQLAlchemy;
2. sem drift, marque a revisão como aplicada sem executar SQL:
   `alembic stamp head`;
3. com drift, resolva com uma migration específica — nunca recriando a
   baseline.

## Testes

Os testes de integração exigem um PostgreSQL real acessível via
`DATABASE_URL` — não usam SQLite.

```bash
export APP_ENV=test
export ALLOW_TEST_DB_MIGRATIONS=true
export DEV_AUTH_ENABLED=true
export DATABASE_URL="postgresql://usuario:senha@host:porta/banco_de_teste"

.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m pytest
```

- `tests/unit/` — funções puras (cálculos, hashing, normalização, período);
- `tests/integration/` — fluxo HTTP completo contra o Postgres real
  (`httpx.AsyncClient` sobre a app via `ASGITransport`, sem subir um
  servidor de verdade). Todas as tabelas são truncadas automaticamente
  após cada teste (`tests/conftest.py`);
- `tests/contract/` — compara as funções compartilhadas contra vetores
  fixos em `tests/fixtures/contract_vectors.json` (tolerância `1e-9`).

### Autenticação em teste

Com `DEV_AUTH_ENABLED=true` e `APP_ENV != production`, as rotas aceitam um
token de desenvolvimento fixo por perfil, sem precisar de um Keycloak
real:

```bash
curl -H "Authorization: Bearer dev-admin" http://localhost:8000/api/v1/auth/me
curl -H "Authorization: Bearer dev-analyst" http://localhost:8000/api/v1/auth/me
curl -H "Authorization: Bearer dev-viewer" http://localhost:8000/api/v1/auth/me
```

O bypass troca somente "quem é você" — a matriz de permissões
(`app/core/permissions.py`) continua sendo aplicada normalmente por
perfil. `DEV_AUTH_ENABLED=false` (padrão) desativa esse caminho
completamente; fora disso, toda rota de negócio exige um access token
OIDC/Keycloak válido.

## Autenticação Keycloak (produção)

Variáveis necessárias (ver `.env.example`):

```env
KEYCLOAK_ISSUER=https://sso.empresa/realms/<realm>
KEYCLOAK_AUDIENCE=central-indicadores-api
KEYCLOAK_JWKS_URL=              # opcional — descoberto via /.well-known se vazio
KEYCLOAK_ALLOWED_ALGORITHMS=RS256
DEV_AUTH_ENABLED=false
```

Fluxo implementado em `app/core/auth.py`:

1. valida assinatura (JWKS, cacheado e renovado por `kid`), `iss`, `aud`,
   algoritmo permitido (nunca `none`), `exp`;
2. resolve o usuário local por `(authProvider="KEYCLOAK", externalUserId=sub)`
   — nunca por e-mail;
3. se não existir, provisiona just-in-time com perfil `VIEWER` e
   `active=true`;
4. `role` e `active` persistidos no banco continuam sendo a fonte de
   verdade — o token nunca eleva privilégio sozinho;
5. usuário inativo é rejeitado mesmo com token válido (401).

## Matriz de permissões

| Permissão | VIEWER | ANALYST | ADMIN |
|---|:---:|:---:|:---:|
| `indicators:read` | ✓ | ✓ | ✓ |
| `indicators:export` | ✓ | ✓ | ✓ |
| `indicators:edit` |  |  | ✓ |
| `indicators:publish` |  |  | ✓ |
| `import:run` |  | ✓ | ✓ |
| `import:read` |  | ✓ | ✓ |
| `users:manage` |  |  | ✓ |
| `audit:read` |  |  | ✓ |
| `settings:manage` |  |  | ✓ |

## Exemplos `curl`

```bash
# Health
curl http://localhost:8000/api/v1/health/live
curl http://localhost:8000/api/v1/health/ready

# Identidade atual
curl -H "Authorization: Bearer dev-admin" http://localhost:8000/api/v1/auth/me

# Painel Geral
curl -H "Authorization: Bearer dev-viewer" http://localhost:8000/api/v1/dashboard

# RDO — leitura
curl -H "Authorization: Bearer dev-viewer" "http://localhost:8000/api/v1/rdo?periodStartYear=2027&periodStartMonth=6&periodEndYear=2027&periodEndMonth=11"

# Iniciar uma importação (RDO)
curl -X POST -H "Authorization: Bearer dev-analyst" -H "Content-Type: application/json" \
  -d '{"module":"rdo","fileName":"planilha.xlsx","totalFound":2}' \
  http://localhost:8000/api/v1/importacoes/iniciar
```

Ver [`../docs/api.md`](../docs/api.md) para a lista completa de rotas.

## Docker

```bash
# Build + subir API e Postgres de desenvolvimento juntos
docker compose up --build
```

O `docker-compose.yml` sobe um Postgres vazio de propósito — ele **não**
roda `alembic upgrade head` automaticamente dentro do container (nunca
migrar silenciosamente). Depois do `up`, rode as migrations e o seed uma
única vez dentro do container da API:

```bash
docker compose exec api python -m alembic upgrade head
docker compose exec api python scripts/seed.py
```

```bash
# Só a imagem da API (aponte DATABASE_URL para um Postgres externo já migrado)
docker build -t central-indicadores-backend .
docker run -p 8000:8000 --env-file .env central-indicadores-backend
```

## Estrutura

```text
backend/
├── app/
│   ├── main.py              # instância FastAPI, middlewares, exception handlers
│   ├── api/v1/               # roteador agregador (/api/v1)
│   ├── core/                 # config, database, auth, permissions, errors, logging
│   ├── models/                # SQLAlchemy — mapeiam as tabelas do Postgres
│   ├── modules/                # um pacote por módulo de negócio
│   │   ├── imports/             # motor de importação incremental genérico
│   │   ├── rdo/ idp/ rnc/ cinco_s/ taxa_acidentes/
│   │   ├── scorecard/ dashboard/
│   │   └── users/ settings/ audit/ indicators/ justifications/
│   └── shared/                 # period, hashing, normalization, dates, units,
│                                 batching, audit, publication_cycle, pagination,
│                                 schema (CamelModel), incremental_upsert
├── alembic/                    # migrations
├── scripts/                    # seed, drift check, openapi export
├── tests/{unit,integration,contract,fixtures}/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

Cada módulo de indicador separa `types.py` (constantes/metas), `schemas.py`
(Pydantic), `keys.py` (business key/content hash), `calculations.py`
(funções puras), `repository.py` (acesso a dados), `service.py`
(orquestração, recálculo), `publications.py` (payload de publicação),
`router.py` (endpoints FastAPI) — regra de negócio nunca fica direto no
router.
