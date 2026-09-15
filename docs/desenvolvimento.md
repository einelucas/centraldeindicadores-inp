# Guia de desenvolvimento

## Ambiente local

Requisitos:

- Node.js 20+;
- pnpm;
- Python 3.12+;
- PostgreSQL.

### Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv/Scripts/python.exe -m pip install -e ".[dev]"

# Linux/macOS
# .venv/bin/python -m pip install -e ".[dev]"

cp .env.example .env
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe scripts/seed.py
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

### Frontend

Em outro terminal:

```bash
cd frontend
pnpm install
cp .env.example .env
pnpm dev
```

Por padrão:

- frontend: `http://localhost:3000`;
- backend: `http://localhost:8000`;
- Swagger: `http://localhost:8000/docs`.

## Convenções de arquitetura

- regra de negócio vive no backend, não em componentes Vue;
- routers FastAPI orquestram HTTP e dependências, mas não concentram cálculo;
- cálculos devem ser determinísticos e testáveis isoladamente;
- validação de entrada deve acontecer nos contratos Pydantic e nos pontos de normalização adequados;
- frontend consome somente APIs e contratos próprios da aplicação;
- banco é acessado somente pelo backend;
- importação, cálculo, publicação e leitura publicada são etapas distintas;
- ações administrativas relevantes devem gerar auditoria quando aplicável;
- permissões são sempre verificadas no servidor.

## Frontend

Use as convenções do Nuxt e priorize componentes compartilhados.

Antes de criar um componente novo:

1. procure equivalente em `frontend/components/`;
2. verifique `components/ui`, `components/filters`, `components/charts` e `components/indicators`;
3. reutilize padrões de `ModuleWorkspace` para módulos com Painel/Administração;
4. mantenha filtros, cards, estados vazios e toolbars coerentes com os demais módulos.

Gráficos compartilhados devem manter comportamento e acabamento consistentes entre indicadores, incluindo hover, tooltip, meta, responsividade e formatação numérica.

## Backend

Estrutura típica de um módulo de indicador:

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

Nem todo módulo precisa de todos os arquivos; a separação deve acompanhar a complexidade real do domínio.

## Adicionando um novo indicador

Checklist recomendado:

1. definir fonte de dados;
2. definir período operacional;
3. definir unidade, direção e meta;
4. definir business key/content hash quando houver importação incremental;
5. implementar validação e normalização;
6. implementar cálculo puro;
7. implementar persistência e serviço;
8. expor endpoints FastAPI;
9. criar a publicação versionada;
10. criar Painel/Administração no frontend quando aplicável;
11. integrar ao Painel Geral/Scorecard somente se fizer parte da regra oficial;
12. cobrir cálculo e fluxo HTTP com testes.

Não reserve peso, meta ou participação no Scorecard sem uma definição explícita de negócio.

## Banco de teste

A suíte de integração deve usar um PostgreSQL dedicado a testes.

Nunca use o mesmo banco da aplicação local/ambiente real para testes que executam limpeza de tabelas.

Verifique `backend/.env.test.example` antes de executar a suíte pela primeira vez.

## Qualidade

### Backend

```bash
cd backend
.venv/Scripts/python.exe -m ruff check app tests scripts
.venv/Scripts/python.exe -m mypy app
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m pytest --cov=app --cov-report=term-missing
```

### Frontend

```bash
cd frontend
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

## Critérios antes de integrar alterações

- lint e typecheck sem erros relevantes;
- testes relacionados à alteração aprovados;
- build do frontend aprovado;
- nenhuma credencial ou segredo versionado;
- alteração de banco acompanhada de migration Alembic revisável;
- contratos frontend/backend compatíveis;
- nenhuma dependência em tecnologia ou código externo ao stack atual;
- documentação atualizada quando houver alteração funcional, estrutural ou de regra de negócio.
