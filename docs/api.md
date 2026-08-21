# API

Toda rota vive sob o prefixo `/api/v1`. Documentação interativa gerada
automaticamente pelo FastAPI: `/docs` (Swagger UI), `/redoc` e
`/openapi.json` (schema bruto), com o servidor local rodando.

Toda rota de negócio exige autenticação e a permissão correspondente,
verificadas no servidor — ver `docs/autenticacao.md`.

## Saúde

```text
GET /health/live      liveness (a API está de pé)
GET /health/ready       readiness (a API consegue falar com o banco)
GET /auth/me            identidade e permissões do usuário autenticado
```

## Painel Geral e Scorecard

```text
GET  /dashboard                                monta o Painel Geral a partir das publicações ativas
GET  /available-periods                        lista os períodos/ciclos disponíveis para os seletores

GET  /scorecard?year=&month=                    consolida um mês (ao vivo, com snapshot salvo como respaldo)
POST /scorecard                                  salva um snapshot com os valores ao vivo do mês informado
GET  /scorecard/history?periodStartYear=&...     lista os snapshots salvos do ciclo
DELETE /scorecard/history?periodStartYear=&...   apaga os snapshots salvos do ciclo (ADMIN)
GET  /scorecard/panel-period                      lê o ciclo usado pelo Painel Geral
PATCH /scorecard/panel-period                      define o ciclo usado pelo Painel Geral
```

## Módulos de indicador

Cada módulo segue o mesmo formato: leitura/edição administrativa em
`/<modulo>`, exclusão em massa em `/<modulo>/registros`, publicação em
`/publicacoes/<modulo>`.

```text
GET|PATCH        /rdo
GET|PATCH|DELETE /rdo/registros

GET              /idp
GET|DELETE       /idp/registros

GET|PATCH        /rnc
GET|PATCH|DELETE /rnc/registros

GET|PATCH        /cinco-s
GET|DELETE       /cinco-s/registros

GET|POST|PATCH|DELETE /taxa-acidentes
GET|DELETE             /taxa-acidentes/registros

GET|POST  /publicacoes/rdo
GET|POST  /publicacoes/idp
GET|POST  /publicacoes/rnc
GET|POST  /publicacoes/cinco-s
GET|POST  /publicacoes/taxa-acidentes
```

`GET .../registros` retorna a contagem de registros afetados por um
período (ou pela base inteira); `DELETE` no mesmo caminho executa a
exclusão — nunca da publicação vigente. Ver `docs/importacao.md`.

## Importação

```text
POST /importacoes/iniciar             cria um job de importação, retorna importJobId
POST /importacoes/{id}/lotes           processa um lote de registros normalizados
POST /importacoes/{id}/finalizar       conclui o job e recalcula o módulo
GET  /importacoes/{id}                 status e detalhe de um job
GET  /importacoes/{id}/erros           erros de linha do job
GET  /importacoes                       lista jobs
```

Taxa de Acidentes não usa este fluxo — seus lançamentos são feitos direto
por `POST /taxa-acidentes`.

## Administração geral

```text
GET       /indicadores                     leitura consolidada para telas administrativas
GET|PATCH /configuracoes                    metas, listas de exclusão e demais parâmetros
GET|POST  /usuarios                         lista/cria usuários (ADMIN)
PATCH     /usuarios/{id}                    edita nome/perfil/status (ADMIN)
GET       /auditoria                        trilha de auditoria (ADMIN)
GET|PUT|DELETE /justificativas              justificativa textual por indicador/competência
GET       /justificativas/sugestao          sugestão recalculada a partir dos dados do módulo
```

## Exemplos

```bash
curl http://localhost:8000/api/v1/health/live

curl -H "Authorization: Bearer dev-admin" http://localhost:8000/api/v1/auth/me

curl -H "Authorization: Bearer dev-viewer" http://localhost:8000/api/v1/dashboard

curl -H "Authorization: Bearer dev-viewer" "http://localhost:8000/api/v1/rdo?periodStartYear=2027&periodStartMonth=6&periodEndYear=2027&periodEndMonth=11"

curl -X POST -H "Authorization: Bearer dev-analyst" -H "Content-Type: application/json" \
  -d '{"module":"rdo","fileName":"planilha.xlsx","totalFound":2}' \
  http://localhost:8000/api/v1/importacoes/iniciar
```
