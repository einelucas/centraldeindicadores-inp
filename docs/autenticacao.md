# Autenticação e permissões

A Central de Indicadores usa **OIDC/Keycloak** para autenticação corporativa. A autorização é controlada pelo backend com base no perfil persistido do usuário.

## Fluxo de autenticação

1. o frontend Nuxt inicia o fluxo OIDC;
2. o usuário autentica no Keycloak;
3. o frontend recebe o access token;
4. chamadas à API enviam `Authorization: Bearer <token>`;
5. o FastAPI valida assinatura, emissor, audiência, algoritmo e expiração;
6. o usuário local é resolvido pelo identificador externo do provedor;
7. perfil (`role`) e status (`active`) persistidos no PostgreSQL definem a autorização efetiva.

O e-mail não deve ser usado como identidade técnica primária quando o `sub` do provedor está disponível.

## Provisionamento

Quando uma identidade Keycloak válida ainda não possui usuário local, o backend pode provisionar a conta automaticamente com o perfil inicial configurado pela aplicação.

A elevação de privilégio não vem do token por si só: o backend continua usando o perfil armazenado localmente como fonte de verdade.

## Variáveis do backend

```env
KEYCLOAK_ISSUER=https://sso.empresa/realms/<realm>
KEYCLOAK_AUDIENCE=central-indicadores-api
KEYCLOAK_JWKS_URL=
KEYCLOAK_ALLOWED_ALGORITHMS=RS256
DEV_AUTH_ENABLED=false
```

`KEYCLOAK_JWKS_URL` pode ser descoberto a partir do issuer quando a configuração do ambiente permitir.

## Variáveis do frontend

```env
NUXT_PUBLIC_OIDC_ISSUER=
NUXT_PUBLIC_OIDC_CLIENT_ID=
NUXT_PUBLIC_OIDC_REDIRECT_URI=http://localhost:3000/auth/callback
NUXT_PUBLIC_OIDC_POST_LOGOUT_REDIRECT_URI=http://localhost:3000/login
NUXT_PUBLIC_DEV_AUTH_ENABLED=true
```

## Desenvolvimento sem Keycloak

Em ambiente de desenvolvimento, a aplicação possui um modo explícito de autenticação local.

Backend:

```env
DEV_AUTH_ENABLED=true
```

Frontend:

```env
NUXT_PUBLIC_DEV_AUTH_ENABLED=true
```

Quando habilitado em ambiente permitido, é possível testar os perfis locais com tokens de desenvolvimento:

```bash
curl -H "Authorization: Bearer dev-viewer" \
  http://localhost:8000/api/v1/auth/me

curl -H "Authorization: Bearer dev-analyst" \
  http://localhost:8000/api/v1/auth/me

curl -H "Authorization: Bearer dev-admin" \
  http://localhost:8000/api/v1/auth/me
```

Esse modo altera somente a forma de identificar o usuário. A matriz de permissões continua sendo aplicada normalmente.

## Perfis

### VIEWER

Voltado para consulta.

Pode, conforme a permissão exposta pelo backend:

- visualizar painéis publicados;
- consultar dados consolidados;
- exportar painéis.

### ANALYST

Voltado para operação administrativa dos indicadores.

Além das permissões de leitura, pode acessar operações como importação e histórico quando autorizado pela matriz do backend.

### ADMIN

Perfil administrativo completo.

Pode incluir:

- publicação de indicadores;
- gerenciamento de usuários;
- configurações;
- auditoria;
- exclusões administrativas permitidas.

## Matriz de permissões

A fonte de verdade está em `backend/app/core/permissions.py`.

Permissões relevantes incluem:

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

A interface pode esconder controles sem permissão, mas isso é apenas UX. Toda ação protegida precisa ser recusada pelo backend quando o usuário não possui a permissão necessária.

## Sessão no frontend

O estado de autenticação é mantido pela store Pinia do frontend. O cliente HTTP da aplicação inclui o token nas chamadas protegidas.

As rotas Nuxt usam middleware para exigir autenticação e, quando necessário, restringir páginas administrativas.

## Segurança

- nunca versionar tokens ou segredos;
- nunca confiar apenas no papel informado pelo cliente;
- validar JWT no backend;
- rejeitar usuário local inativo mesmo com token válido;
- não conceder privilégio automaticamente a partir de claims não aprovadas pela regra da aplicação;
- manter URLs e client IDs específicos de ambiente nas variáveis de configuração.
