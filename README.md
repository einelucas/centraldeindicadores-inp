# Central de Indicadores

Aplicação web para importar, calcular, publicar e acompanhar indicadores
operacionais em um único ambiente. O sistema separa o processamento
administrativo dos painéis de consulta, mantém histórico versionado de
publicações e consolida o desempenho do ciclo em um scorecard.

## Indicadores disponíveis

1. **RDO** — aprovação de relatórios diários de obra;
2. **IDP** — aderência ao cronograma por disciplina;
3. **RNC** — prazo e aderência de tratativa de não conformidades;
4. **5S** — aderência do programa 5S por unidade;
5. **Taxa de Acidentes** — frequência de acidentes por unidade;
6. **Scorecard** — consolida os cinco indicadores acima por ciclo semestral.

Veja `docs/modulos.md` para o que cada um calcula e `docs/scorecard.md`
para as regras de pontuação.

## Principais recursos

- autenticação corporativa (Keycloak/OIDC) e controle de acesso por perfil;
- importação de planilhas Excel/CSV e PDFs, com leitura no navegador;
- deduplicação e atualização incremental por business key + content hash;
- cálculo por indicador, unidade e período;
- publicação versionada de resultados (snapshots imutáveis);
- painéis de consulta separados da área administrativa;
- exportações em Excel e PDF;
- auditoria de operações administrativas.

## Stack

| Camada | Tecnologia |
|---|---|
| Frontend | Nuxt 4, Vue 3, TypeScript, Pinia |
| Backend | FastAPI, Pydantic, SQLAlchemy assíncrono |
| Banco de dados | PostgreSQL |
| Migrations | Alembic |
| Autenticação | Keycloak (OIDC) |
| Planilhas/PDF | SheetJS (XLSX), pdf.js |
| Exportação | jsPDF + html2canvas, SheetJS |
| Testes | pytest (backend), Vitest (frontend) |

## Estrutura do repositório

```text
backend/     API FastAPI — regra de negócio, cálculo, persistência
frontend/    Aplicação Nuxt — telas e painéis
docs/        Documentação técnica
public/      Assets estáticos servidos pelo frontend
```

## Executando localmente

Requisitos: Node.js 20+, pnpm, Python 3.12+ e um PostgreSQL acessível
(local ou via `backend/docker-compose.yml`).

```bash
# Banco (Postgres local, vazio)
cd backend
docker compose up -d postgres

# Backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"   # Windows
cp .env.example .env
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe scripts/seed.py
.venv/Scripts/python.exe -m uvicorn app.main:app --reload

# Frontend (em outro terminal, a partir de frontend/)
cd frontend
pnpm install
cp .env.example .env
pnpm dev
```

Backend em `http://localhost:8000` (`/docs` para a API interativa),
frontend em `http://localhost:3000`. Com `DEV_AUTH_ENABLED=true` nos dois
lados, a tela de login permite entrar sem um Keycloak real — veja
`docs/autenticacao.md`.

## Perfis de acesso

| Perfil | Acesso principal |
|---|---|
| `VIEWER` | Consulta e exportação dos painéis publicados |
| `ANALYST` | Também importa, edita dados administrativos e publica indicadores |
| `ADMIN` | Também gerencia usuários, configurações e audita o sistema |

Permissões são sempre verificadas no servidor. Ver `docs/autenticacao.md`
para a matriz completa.

## Fluxo de um indicador

```text
Arquivo ou lançamento manual
        ↓
Leitura e normalização (navegador)
        ↓
Validação e deduplicação (API)
        ↓
Persistência no PostgreSQL
        ↓
Cálculo administrativo
        ↓
Publicação de snapshot
        ↓
Painel do indicador → Painel Geral → Scorecard
```

Os painéis de consulta sempre leem publicações — uma alteração na
Administração só aparece no painel depois de uma nova publicação.

## Documentação

A documentação técnica completa está em [`docs/README.md`](docs/README.md):
arquitetura, módulos, autenticação, banco de dados, API e guia de
desenvolvimento. O backend tem seu próprio guia detalhado em
[`backend/README.md`](backend/README.md).
