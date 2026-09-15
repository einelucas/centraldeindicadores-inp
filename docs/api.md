# API

A API da Central de Indicadores é fornecida pelo FastAPI e usa o prefixo `/api/v1`.

Com o backend em execução:

- Swagger UI: `/docs`;
- ReDoc: `/redoc`;
- OpenAPI: `/openapi.json`.

As rotas de negócio exigem autenticação e a permissão correspondente.

## Saúde e autenticação

```text
GET /api/v1/health/live
GET /api/v1/health/ready
GET /api/v1/auth/me
```

## Painel Geral

```text
GET /api/v1/dashboard
GET /api/v1/available-periods
```

O Painel Geral é montado a partir das publicações disponíveis para o ciclo selecionado.

## Scorecard

```text
GET    /api/v1/scorecard
POST   /api/v1/scorecard
GET    /api/v1/scorecard/history
DELETE /api/v1/scorecard/history
GET    /api/v1/scorecard/panel-period
PATCH  /api/v1/scorecard/panel-period
```

Responsabilidades:

- consolidar os resultados mensais dos indicadores oficiais;
- calcular pontos possíveis e realizados;
- salvar snapshots de respaldo;
- consultar/limpar histórico;
- definir o ciclo utilizado no Painel Geral.

## RDO

```text
GET    /api/v1/rdo
PATCH  /api/v1/rdo
GET    /api/v1/rdo/registros
PATCH  /api/v1/rdo/registros
DELETE /api/v1/rdo/registros

GET  /api/v1/publicacoes/rdo
POST /api/v1/publicacoes/rdo
```

## IDP

```text
GET    /api/v1/idp
GET    /api/v1/idp/registros
DELETE /api/v1/idp/registros

GET  /api/v1/publicacoes/idp
POST /api/v1/publicacoes/idp
```

## RNC

```text
GET    /api/v1/rnc
PATCH  /api/v1/rnc
GET    /api/v1/rnc/registros
PATCH  /api/v1/rnc/registros
DELETE /api/v1/rnc/registros

GET  /api/v1/publicacoes/rnc
POST /api/v1/publicacoes/rnc
```

## 5S

O backend mantém rotas do domínio 5S para os dados existentes e sua infraestrutura administrativa:

```text
GET    /api/v1/cinco-s
PATCH  /api/v1/cinco-s
GET    /api/v1/cinco-s/registros
DELETE /api/v1/cinco-s/registros

GET  /api/v1/publicacoes/cinco-s
POST /api/v1/publicacoes/cinco-s
```

A interface dedicada do 5S está atualmente em estado informativo e o indicador não participa do Scorecard.

## Horas Extras Pagas

A interface de Horas Extras está preparada no frontend, mas ainda não possui fonte de dados e API operacional própria para importação/cálculo. Seu peso de 10% permanece reservado no Scorecard.

## Importações

### Upload direto

Usado pelos módulos que possuem parser de arquivo no backend, como RDO e RNC:

```text
POST /api/v1/importacoes/{modulo}/arquivos
```

### Jobs em lotes

```text
POST /api/v1/importacoes/iniciar
POST /api/v1/importacoes/{id}/lotes
POST /api/v1/importacoes/{id}/finalizar
GET  /api/v1/importacoes/{id}
GET  /api/v1/importacoes/{id}/erros
GET  /api/v1/importacoes
```

Veja [`importacao.md`](importacao.md).

## Indicadores e configurações

```text
GET       /api/v1/indicadores
GET|PATCH /api/v1/configuracoes
```

As configurações incluem metas e parâmetros persistidos usados pelos módulos.

## Usuários

```text
GET  /api/v1/usuarios
POST /api/v1/usuarios
PATCH /api/v1/usuarios/{id}
```

O gerenciamento de usuários exige perfil autorizado.

## Auditoria

```text
GET /api/v1/auditoria
```

Retorna a trilha de ações administrativas registrada pelo backend.

## Justificativas

As justificativas são disponibilizadas para os módulos operacionais suportados pela implementação atual.

```text
GET    /api/v1/justificativas
PUT    /api/v1/justificativas
DELETE /api/v1/justificativas
GET    /api/v1/justificativas/sugestao
```

A sugestão é gerada a partir dos dados do próprio módulo; não é um texto fixo.

## Exemplos

```bash
curl http://localhost:8000/api/v1/health/live

curl -H "Authorization: Bearer dev-admin" \
  http://localhost:8000/api/v1/auth/me

curl -H "Authorization: Bearer dev-viewer" \
  http://localhost:8000/api/v1/dashboard

curl -H "Authorization: Bearer dev-viewer" \
  "http://localhost:8000/api/v1/rdo?periodStartYear=2027&periodStartMonth=6&periodEndYear=2027&periodEndMonth=11"
```

## Fonte de verdade

O agregador de rotas está em `backend/app/api/v1/router.py`. Para contratos exatos de request/response, consulte o OpenAPI gerado pela aplicação e os schemas Pydantic de cada módulo.
