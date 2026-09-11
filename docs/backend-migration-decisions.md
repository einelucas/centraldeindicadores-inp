# Decisões da migração do backend (Next → FastAPI)

Este documento existe porque várias partes do código em `backend/` citam
`docs/backend-migration-decisions.md` como a fonte de uma decisão, mas o
arquivo nunca tinha sido criado — as citações apontavam para lugar nenhum.
Este documento consolida, com evidência de código, cada decisão realmente
tomada. Onde uma decisão muda o comportamento observável em relação ao
TypeScript original (Next) e não há registro de validação por alguém do
time de negócio, isso é dito explicitamente — citar este arquivo não deve
ser lido como "decisão aprovada" quando o texto diz o contrário.

## §1 — Isolamento do banco de dados de teste (incidente registrado)

**O que aconteceu:** `backend/tests/conftest.py` sempre teve uma fixture
`autouse` que executa `TRUNCATE TABLE ... RESTART IDENTITY CASCADE` em todas
as tabelas da aplicação após cada teste. Até esta correção, essa fixture
usava o mesmo `engine`/`DATABASE_URL` de `backend/.env` — o mesmo arquivo
usado pelo servidor de desenvolvimento real. Como não existia um banco de
teste fisicamente separado, rodar a suíte de testes (algo pedido como
critério de conclusão em toda adequação/migração de módulo) apagava todos os
dados reais inseridos manualmente no sistema. Isso já aconteceu mais de uma
vez, incluindo durante a auditoria do módulo IDP.

**Correção aplicada:**

- `backend/tests/conftest.py` agora carrega `backend/.env.test` (com
  `override=True`) **antes** de importar qualquer coisa de `app.*`, e recusa
  explicitamente a rodar se esse arquivo não existir.
- Foi criado um banco Postgres fisicamente separado (`neondb_test`, no mesmo
  servidor Neon do banco real) só para a suíte de testes, com o schema
  aplicado via `alembic upgrade head`.
- `_clean_database` agora verifica `SELECT current_database()` e o
  `APP_ENV` resolvido antes de truncar — se o banco conectado não terminar
  em `_test` ou `APP_ENV != "test"`, a fixture levanta um erro em vez de
  truncar. Isso é uma segunda trava, independente do `.env.test` estar
  correto, para que uma reconfiguração futura não repita o incidente.
- `backend/.env.test.example` documenta o requisito para quem for configurar
  o ambiente pela primeira vez.

**Regra permanente:** `backend/.env` (servidor de desenvolvimento, dados
reais) e `backend/.env.test` (suíte de testes, banco descartável) nunca
podem apontar para o mesmo banco de dados. Nenhuma migração/adequação de
módulo deve alterar essa separação.

## §2 — Por que não usar SQLite nos testes

Os testes de integração exercitam comportamento específico do PostgreSQL
(constraints, tipos JSON, `TRUNCATE ... CASCADE`, índices únicos parciais)
que SQLite não reproduz fielmente. A suíte sempre exigiu um Postgres real
(ver `backend/tests/conftest.py`); a alternativa (SQLite em memória) foi
descartada para não mascarar divergências de comportamento entre o banco de
teste e o de produção.

## §3.3 — Escopo da fixture de event loop do pytest-asyncio

`pyproject.toml`: `asyncio_default_fixture_loop_scope = "function"` (não
`"session"`). Com escopo `"session"`, o event loop é compartilhado entre
testes, e o `NullPool` assíncrono do `asyncpg` (necessário para que cada
teste abra uma conexão nova presa ao loop correto — ver
`app/core/database.py`) causava execução duplicada de testes e hangs
intermitentes quando uma conexão de um teste anterior ficava presa a um loop
já encerrado. Escopo `"function"` isola cada teste em seu próprio loop.

## §4.2.1 — IDP: `calculate_idp_adherence` com `previsto == 0`

**Status: RESOLVIDO — revertido para paridade com o Next (2026-09-10).**

- TS original (`src/features/idp/calculations/index.ts:51-54`): quando
  `previsto` é `0` ou não finito, retorna `0`.
- Uma sessão de adequação anterior havia mudado o Python para retornar
  `None` nesse caso, citando este documento como se a decisão já estivesse
  registrada e aprovada — o que não era verdade, pois o documento não
  existia. Isso fazia `average_ignoring_none` **excluir** unidades com
  baseline zerado da aderência geral, em vez de **incluí-las como zero**
  (comportamento do `average()` do TS), alterando silenciosamente números
  publicados em relação ao legado.
- Consultado o responsável pelo projeto em 2026-09-10: decisão confirmada
  de restaurar o comportamento original do Next. `calculate_idp_adherence`
  (`backend/app/modules/idp/calculations.py:49-57`) agora retorna `0.0`
  (não mais `None`) quando `previsto == 0` ou não finito — paridade total
  restaurada. Teste correspondente:
  `backend/tests/unit/test_idp_calculations.py::test_baseline_zero_retorna_zero`.

## §4.2.2 — IDP: seleção de competência sem período informado

`backend/app/modules/idp/calculations.py:262-266`: quando `GET /idp` é
chamado sem filtro de período, usa a competência mais recente disponível em
toda a base como "mês do histórico"; se não houver nenhum registro, usa o
mês/ano atual do servidor. Esse ramo (ausência total de período) não tinha
um teste unitário correspondente no TS original disponível no inventário —
decisão pragmática para preencher uma lacuna de especificação, não uma
divergência deliberada de comportamento.

## §4.2.3 — IDP: serialização de estruturas aninhadas no hash de conteúdo

`backend/app/modules/idp/keys.py`: os campos `areas`/`discData`/
`execucaoFases` do RSO são listas/objetos aninhados, não escalares. O
inventário do TS original não deixou claro como `makeContentHash` (que
documentadamente faz `String(value)` sobre cada campo) serializava esses
valores sem perder sensibilidade do hash a mudanças de conteúdo. A
implementação Python serializa cada estrutura via
`json.dumps(..., sort_keys=True)` antes de entrar no hash — garante
determinismo e sensibilidade real a mudanças, mesmo sem garantia de que o
valor do hash seja bit-a-bit idêntico ao do TS original (o que não é um
requisito funcional: o hash só precisa ser estável e sensível a mudanças
para o motor de importação incremental funcionar).

## §4.2.4 — IDP: linha corrompida na reidratação não derruba a rota

`backend/app/modules/idp/repository.py`: ao reidratar registros persistidos
do RSO para `IdpNormalizedRecord`, uma linha corrompida (dado inconsistente
no banco) é ignorada e contada separadamente, em vez de propagar uma
exceção não tratada que derrubaria a rota inteira com 500. Correção
mandatória em relação ao comportamento observado no `HEAD` da migração
(que não tratava esse caso).

## §4.2.6 — IDP: `idp.excludedDisciplines` aceita string ou array

`backend/app/modules/idp/router.py:466-471`: o setting
`idp.excludedDisciplines` é aceito tanto como string multi-linha (textarea
do admin, um nome por linha ou separado por vírgula) quanto como array já
pronto. O inventário do TS original só confirmou, via teste unitário, o
comportamento de split de string — o suporte a array direto é uma extensão
pragmática para tolerar ambos os formatos sem quebrar compatibilidade.

## RNC — `dataSolucao` não parseável não rejeita o registro

`backend/app/modules/rnc/service.py`: quando `dataCriacao` não é parseável,
o registro é rejeitado (mesmo comportamento do TS:
`rncRecordSchema.safeParse` falha, ou `new Date(...)` é `NaN`). Já
`dataSolucao`, quando presente mas não parseável, não rejeita a linha —
fica `None` (equivale a "ainda não solucionada"). O TS original não tinha
um caminho de rejeição explícito para esse campo especificamente, então
esse comportamento é uma extrapolação razoável, não uma divergência
deliberada.
