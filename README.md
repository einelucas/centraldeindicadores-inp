# Central de Indicadores

Aplicação web corporativa para importar, calcular, publicar e acompanhar indicadores operacionais em um único ambiente. O frontend é desenvolvido em **Nuxt 4 + Vue 3 + TypeScript** e consome uma API **FastAPI** responsável por autenticação, regras de negócio, cálculos, persistência e auditoria.

A aplicação separa dados administrativos dos painéis publicados: importações, ajustes e cálculos ficam na área de Administração; os painéis de consulta exibem somente publicações versionadas.

## Módulos existentes

| Módulo | Finalidade | Scorecard |
|---|---|---:|
| **RDO** | Aprovação dos Relatórios Diários de Obra por unidade e período | 35% |
| **IDP / Cronograma** | Aderência da execução física ao cronograma por disciplina, unidade e período | 40% |
| **RNC** | Prazo médio de tratativa das não conformidades e acompanhamento por unidade | 15% |
| **Horas Extras Pagas** | Indicador de RH com interface preparada e regras parciais de referência | 10% reservado |
| **5S** | Área própria do programa 5S; atualmente exibida como "Em breve" | Fora do Scorecard |
| **Scorecard** | Consolidação semestral dos indicadores oficiais e da pontuação do ciclo | — |
| **Painel Geral** | Visão consolidada das publicações vigentes | — |

O módulo **Horas Extras Pagas** possui peso oficial de 10% reservado, mas ainda não altera a pontuação consolidada. A interface já apresenta a direção do indicador, a meta de referência `≤ 1%` e a faixa de 80% `> 1% e ≤ 2%`, enquanto a fonte de dados e a fórmula operacional completa permanecem em desenvolvimento.

Veja [`docs/modulos.md`](docs/modulos.md) para o detalhamento funcional e [`docs/scorecard.md`](docs/scorecard.md) para as regras de pontuação.

## Principais recursos

- autenticação corporativa via Keycloak/OIDC;
- controle de acesso por perfil (`VIEWER`, `ANALYST`, `ADMIN`);
- importação de planilhas Excel/CSV e arquivos usados pelos módulos suportados;
- validação, normalização, deduplicação e persistência incremental;
- cálculo por indicador, unidade e período;
- publicação versionada de resultados;
- filtros por ciclo e unidade nos painéis publicados;
- exportação dos painéis em PDF e dados administrativos em formatos compatíveis;
- justificativas para os módulos operacionais suportados;
- trilha de auditoria das ações administrativas;
- Scorecard semestral com snapshots de respaldo.

## Stack

| Camada | Tecnologia |
|---|---|
| Frontend | Nuxt 4, Vue 3, TypeScript, Pinia, Tailwind CSS |
| Backend | FastAPI, Pydantic v2, SQLAlchemy assíncrono |
| Banco de dados | PostgreSQL |
| Versionamento de schema | Alembic |
| Autenticação | Keycloak / OIDC |
| Arquivos | openpyxl, xlrd, pyxlsb, SheetJS quando aplicável |
| Exportação | jsPDF + html2canvas |
| Testes | pytest / pytest-asyncio / Vitest |

## Arquitetura do repositório

```text
centraldeindicadores-inp/
├── backend/       # API FastAPI, regras de negócio, persistência e testes
├── frontend/      # aplicação Nuxt/Vue
├── docs/          # documentação técnica e funcional
├── AGENTS.md      # convenções obrigatórias para alterações no projeto
└── README.md
```

O frontend nunca acessa o banco diretamente. Toda comunicação de dados passa pela API FastAPI em `/api/v1`.

## Executando localmente

Requisitos principais: Node.js 20+, pnpm, Python 3.12+ e PostgreSQL.

```bash
# Backend
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"
cp .env.example .env
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe scripts/seed.py
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

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
- Swagger: `http://localhost:8000/docs`;
- OpenAPI: `http://localhost:8000/openapi.json`.

Para desenvolvimento sem um servidor Keycloak, consulte [`docs/autenticacao.md`](docs/autenticacao.md).

## Perfis de acesso

| Perfil | Acesso principal |
|---|---|
| `VIEWER` | Consulta e exportação dos painéis publicados |
| `ANALYST` | Importação, operação administrativa e histórico compatível com suas permissões |
| `ADMIN` | Publicação, usuários, configurações, exclusões administrativas e auditoria |

A autorização é validada no backend; esconder um botão na interface nunca substitui a verificação de permissão na API.

## Fluxo dos indicadores operacionais

```text
Arquivo / entrada administrativa
        ↓
Leitura e normalização
        ↓
Validação e deduplicação
        ↓
Persistência no PostgreSQL
        ↓
Cálculo do módulo
        ↓
Publicação versionada
        ↓
Painel do indicador
        ↓
Painel Geral / Scorecard
```

Os painéis publicados não exibem alterações administrativas ainda não publicadas.

## Documentação

A documentação técnica está organizada em [`docs/README.md`](docs/README.md), com detalhes sobre arquitetura, módulos, Scorecard, importações, autenticação, API, banco de dados e desenvolvimento. O backend possui instruções específicas em [`backend/README.md`](backend/README.md).
