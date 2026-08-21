# Autenticação e permissões

## Provedor

A API valida tokens **OIDC emitidos pelo Keycloak**. Não há cadastro nem
login por e-mail/senha na aplicação — a conta é sempre provisionada a
partir de uma identidade corporativa.

Fluxo (`backend/app/core/auth.py`):

1. o frontend redireciona para o Keycloak (`NUXT_PUBLIC_OIDC_ISSUER` +
   `NUXT_PUBLIC_OIDC_CLIENT_ID`), fluxo `authorization_code`;
2. o token de acesso recebido é enviado em `Authorization: Bearer <token>`
   em toda chamada à API;
3. o backend valida assinatura (JWKS, cacheado e renovado por `kid`),
   emissor (`iss`), audiência (`aud`), algoritmo permitido (nunca `none`) e
   expiração;
4. o usuário local é resolvido por `(authProvider="KEYCLOAK",
   externalUserId=sub)` — nunca por e-mail;
5. se a conta ainda não existe, é provisionada automaticamente (JIT) com
   perfil inicial `VIEWER`;
6. `role` e `active` **persistidos no banco** são sempre a fonte de
   verdade — um token nunca eleva privilégio sozinho, e uma conta
   desativada é rejeitada mesmo com token Keycloak válido.

Variáveis de ambiente do backend (`backend/.env`):

```env
KEYCLOAK_ISSUER=https://sso.empresa/realms/<realm>
KEYCLOAK_AUDIENCE=central-indicadores-api
KEYCLOAK_JWKS_URL=              # opcional — descoberto via /.well-known se vazio
KEYCLOAK_ALLOWED_ALGORITHMS=RS256
```

Variáveis do frontend (`frontend/.env`):

```env
NUXT_PUBLIC_OIDC_ISSUER=
NUXT_PUBLIC_OIDC_CLIENT_ID=
NUXT_PUBLIC_OIDC_REDIRECT_URI=http://localhost:3000/auth/callback
NUXT_PUBLIC_OIDC_POST_LOGOUT_REDIRECT_URI=http://localhost:3000/login
```

## Bypass de desenvolvimento

Para desenvolver e testar sem um Keycloak real, ambos os lados aceitam um
bypass explícito:

```env
# backend/.env
DEV_AUTH_ENABLED=true

# frontend/.env
NUXT_PUBLIC_DEV_AUTH_ENABLED=true
```

Com o bypass ativo (e `APP_ENV` diferente de `production` no backend), a
tela de login mostra três botões (Viewer / Analyst / Admin) que autenticam
com um token fixo por perfil:

```bash
curl -H "Authorization: Bearer dev-admin"   http://localhost:8000/api/v1/auth/me
curl -H "Authorization: Bearer dev-analyst" http://localhost:8000/api/v1/auth/me
curl -H "Authorization: Bearer dev-viewer"  http://localhost:8000/api/v1/auth/me
```

O bypass troca somente "quem é você" — a matriz de permissões abaixo
continua sendo aplicada normalmente. Com `DEV_AUTH_ENABLED=false` (o
padrão), esse caminho fica completamente desativado e toda rota de negócio
exige um token Keycloak válido.

## Perfis e permissões

Três perfis, verificados sempre no servidor (`app/core/permissions.py`) —
nunca apenas ocultando um botão na interface:

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

- **VIEWER** — consulta e exportação dos painéis publicados.
- **ANALYST** — também importa planilhas, edita dados administrativos e
  consulta o histórico de importações.
- **ADMIN** — também publica indicadores, gerencia usuários, configurações
  e consulta a auditoria.

## Sessão no frontend

O token de acesso fica em um cookie (`central_access_token`); o estado de
autenticação vive na store Pinia `stores/auth.ts`, que expõe o usuário
atual, o perfil e os helpers de permissão consumidos pelas telas. Toda
chamada feita por `composables/useApi.ts` inclui o token automaticamente.
