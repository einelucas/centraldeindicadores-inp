# Guia de desenvolvimento

## Ambiente local

Requisitos: Node.js 20+, pnpm, Python 3.12+, PostgreSQL (local ou via
`backend/docker-compose.yml`).

```bash
# 1. Banco (Postgres vazio, local)
cd backend
docker compose up -d postgres

# 2. Backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"   # Windows
# .venv/bin/python -m pip install -e ".[dev]"          # Linux/macOS
cp .env.example .env        # preencha DATABASE_URL
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe scripts/seed.py
.venv/Scripts/python.exe -m uvicorn app.main:app --reload

# 3. Frontend (em outro terminal)
cd frontend
pnpm install
cp .env.example .env         # já aponta para http://localhost:8000
pnpm dev
```

Backend em `http://localhost:8000` (`/docs` para a documentação
interativa); frontend em `http://localhost:3000`. Com
`DEV_AUTH_ENABLED=true` dos dois lados, a tela de login mostra os botões
Viewer/Analyst/Admin sem precisar de um Keycloak real — ver
`docs/autenticacao.md`.

## Convenções

- regra de negócio nunca fica em componente visual nem em router — vive em
  `calculations.py`/`service.py` de cada módulo;
- valide entradas na borda (schemas Pydantic no backend, tipos TypeScript
  no frontend);
- funções de cálculo são puras: recebem dados já normalizados, não
  dependem de banco, HTTP nem do navegador, e são determinísticas;
- mantenha importação, cálculo e publicação como etapas sempre separadas;
- registre em auditoria toda operação administrativa relevante;
- a sub-aba "Painel" de cada indicador é somente leitura; importações e
  ajustes ficam sempre na sub-aba "Administração".

## Adicionando um módulo de indicador

Estrutura recomendada no backend:

```text
app/modules/<modulo>/
├── types.py
├── schemas.py
├── keys.py
├── calculations.py
├── repository.py
├── service.py
├── publications.py
└── router.py
```

E no frontend, reaproveitando os componentes genéricos existentes sempre
que possível:

```text
pages/dashboard/<modulo>.vue          # usa ModuleWorkspace + PublishedPanel + IndicatorAdmin
```

Checklist:

1. definir fonte de dados e colunas aceitas (ou lançamento manual, se não
   houver planilha);
2. definir normalização e período operacional;
3. definir business key e content hash (`docs/importacao.md`);
4. implementar o cálculo puro e cobri-lo com teste unitário;
5. implementar repositório e serviço (persistência + recálculo);
6. expor os endpoints (`router.py`) com a permissão correta;
7. criar a publicação versionada (`publications.py`);
8. integrar ao Painel Geral/Scorecard quando aplicável;
9. cobrir com teste de integração (fluxo HTTP completo).

## Testes

```bash
# Backend, a partir de backend/ (requer PostgreSQL real — ver backend/README.md)
.venv/Scripts/python.exe -m ruff check app tests scripts
.venv/Scripts/python.exe -m mypy app
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m pytest --cov=app --cov-report=term-missing

# Frontend, a partir de frontend/
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

- **Unitários** — funções puras: cálculo, hashing, normalização, período.
  Não usam banco.
- **Integração** (backend) — fluxo HTTP completo contra um PostgreSQL
  real, sem subir um servidor de verdade (`httpx.AsyncClient` via
  `ASGITransport`). Cada teste roda com as tabelas truncadas
  automaticamente ao final.
- **Contrato** (backend) — compara as funções compartilhadas contra
  vetores fixos, garantindo que o comportamento numérico não regrida.

## Critérios antes de um merge

- typecheck e lint sem erros nos dois lados;
- testes relacionados à alteração passando;
- build de produção do frontend aprovado (`pnpm build`);
- nenhuma credencial commitada;
- alteração de banco acompanhada de uma migration revisável (nunca `push`
  direto contra um ambiente compartilhado).
