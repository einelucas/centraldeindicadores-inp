# Banco de dados

PostgreSQL, acessado pelo backend via SQLAlchemy assíncrono (`asyncpg`) e
versionado com Alembic. O frontend nunca acessa o banco diretamente.

## Tabelas principais

- `User` — conta local, com `role` (`VIEWER`/`ANALYST`/`ADMIN`), `active`,
  `authProvider` e `externalUserId` (identidade Keycloak);
- `ImportJob`, `ImportBatch`, `ImportError` — rastreio das importações;
- `IndicatorResult` — resultado administrativo consolidado por módulo,
  unidade, ano e mês;
- `IndicatorPublication` — snapshots versionados exibidos nos painéis de
  leitura e no Scorecard;
- `IndicatorJustification` — justificativas de exclusões/ajustes por
  competência;
- `RdoRecord`, `IdpRsoRecord`, `RncRecord`, `FiveSRecord` — registros
  importados dos módulos com importação de arquivo;
- `AccidentMonthlyRecord`, `AccidentUnitRecord` — lançamentos manuais da
  Taxa de Acidentes (sem importação de arquivo);
- `ScorecardSnapshot` — snapshots mensais salvos manualmente do Scorecard;
- `AppSetting` — metas, listas de exclusão e demais parâmetros por módulo;
- `AuditLog` — trilha de ações administrativas.

`Session`, `Account` e `Verification` seguem no schema por compatibilidade
histórica, mas não são usados pelo fluxo de autenticação atual (Keycloak
não depende de sessão local). `IdpRecord` também existe no schema mas não
tem nenhum uso no código atual — `IdpRsoRecord` é o modelo que o cálculo do
IDP realmente usa.

## Configurações oficiais (`AppSetting`)

| Chave | Valor padrão |
|---|---:|
| `rdo.target` | 0,80 |
| `idp.target` | 0,90 |
| `rnc.maxPrazoDias` | 15 |
| `fiveS.target` | 0,90 |
| `fiveS.excludedUnits` | SP, CSC |
| `taxa-acidentes.target` | 7,5 |

Editáveis pela tela de Configurações da Administração
(`PATCH /api/v1/configuracoes`), sem precisar de deploy.

## Migrations

```bash
# a partir de backend/, com o venv ativado
alembic upgrade head        # aplica migrations pendentes
alembic revision --autogenerate -m "descrição"   # gera uma nova migration
alembic stamp head           # marca a revisão como aplicada sem executar SQL
```

Regras de segurança aplicadas em código (`alembic/env.py`), não apenas em
documentação:

- migrations só executam quando a variável `APP_ENV` do backend é `test`
  ou `development` **e** `ALLOW_TEST_DB_MIGRATIONS=true`; qualquer outra
  combinação interrompe a execução;
- antes de rodar, o host/porta/usuário/banco (nunca a senha) são impressos
  para conferência manual;
- se a URL de conexão contiver qualquer indício textual de produção
  (`prod`, `production`, `prd`), a migration é interrompida.

## Script de apoio

```bash
python scripts/check_schema_drift.py   # compara os modelos SQLAlchemy com o schema real do banco
python scripts/seed.py                  # popera as configurações oficiais + um usuário de teste (idempotente)
```
