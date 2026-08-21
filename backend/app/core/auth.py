"""Autenticação OIDC/JWT (Keycloak) + bypass de desenvolvimento controlado.

Porta o fluxo descrito em `docs/migration-authentication-keycloak.md`:
- valida o access token (assinatura via JWKS, issuer, audience, algoritmo,
  exp/nbf);
- resolve o usuário local por (authProvider, externalUserId) — nunca associa
  automaticamente por e-mail, a menos que o e-mail esteja verificado E o
  provisionamento por e-mail esteja explicitamente habilitado;
- no primeiro acesso, provisiona just-in-time com perfil VIEWER;
- `role`/`active` persistidos no banco continuam sendo a fonte de verdade
  (o token nunca eleva privilégio sozinho).

Bypass de desenvolvimento: só quando `DEV_AUTH_ENABLED=true` e
`APP_ENV != "production"`. Mesmo com o bypass ativo, a matriz de permissões
continua sendo aplicada normalmente — o bypass troca apenas a etapa de
"quem é você", nunca a de "o que você pode fazer".
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import Depends, Request
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.errors import UnauthorizedError
from app.core.permissions import Permission, Role, assert_can
from app.models.user import User

_DEV_TOKEN_ROLES: dict[str, Role] = {
    "dev-viewer": Role.VIEWER,
    "dev-analyst": Role.ANALYST,
    "dev-admin": Role.ADMIN,
}

DEV_AUTH_PROVIDER = "DEV"
KEYCLOAK_AUTH_PROVIDER = "KEYCLOAK"


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: str
    email: str
    name: str
    role: Role
    active: bool


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    issuer: str
    subject: str
    email: str | None
    email_verified: bool
    name: str | None
    preferred_username: str | None
    raw_claims: dict[str, Any]


class _JWKSCache:
    """Cache das chaves JWKS com atualização quando o `kid` não é encontrado."""

    def __init__(self) -> None:
        self._keys: dict[str, Any] = {}
        self._fetched_at: float = 0.0
        self._jwks_uri: str | None = None

    async def _discover_jwks_uri(self, client: httpx.AsyncClient, settings: Settings) -> str:
        if settings.keycloak_jwks_url:
            return settings.keycloak_jwks_url
        if not settings.keycloak_issuer:
            raise UnauthorizedError("Keycloak não configurado")
        discovery_url = settings.keycloak_issuer.rstrip("/") + "/.well-known/openid-configuration"
        response = await client.get(discovery_url, timeout=5.0)
        response.raise_for_status()
        jwks_uri = response.json().get("jwks_uri")
        if not jwks_uri:
            raise UnauthorizedError("Documento de descoberta OIDC sem jwks_uri")
        return jwks_uri

    async def _fetch(self, settings: Settings) -> None:
        async with httpx.AsyncClient() as client:
            if self._jwks_uri is None:
                self._jwks_uri = await self._discover_jwks_uri(client, settings)
            response = await client.get(self._jwks_uri, timeout=5.0)
            response.raise_for_status()
            jwks = response.json()
        self._keys = {key["kid"]: key for key in jwks.get("keys", []) if "kid" in key}
        self._fetched_at = time.monotonic()

    async def get_key(self, kid: str, settings: Settings) -> dict[str, Any]:
        expired = (time.monotonic() - self._fetched_at) > settings.jwks_cache_ttl_seconds
        if kid not in self._keys or expired:
            await self._fetch(settings)
        key = self._keys.get(kid)
        if key is None:
            raise UnauthorizedError("Chave de assinatura desconhecida (kid)")
        return key


_jwks_cache = _JWKSCache()


async def verify_access_token(token: str, settings: Settings) -> AuthenticatedIdentity:
    """Valida assinatura, issuer, audience, algoritmo e validade do token."""
    if not settings.keycloak_issuer or not settings.keycloak_audience:
        raise UnauthorizedError("Autenticação Keycloak não configurada neste ambiente")

    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise UnauthorizedError("Token malformado") from exc

    algorithm = unverified_header.get("alg")
    if algorithm not in settings.keycloak_allowed_algorithms_list:
        raise UnauthorizedError("Algoritmo de assinatura não permitido")

    kid = unverified_header.get("kid")
    if not kid:
        raise UnauthorizedError("Token sem 'kid'")

    key = await _jwks_cache.get_key(kid, settings)

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=settings.keycloak_allowed_algorithms_list,
            audience=settings.keycloak_audience,
            issuer=settings.keycloak_issuer,
            options={"require_exp": True, "require_iat": False, "require_nbf": False},
        )
    except ExpiredSignatureError as exc:
        raise UnauthorizedError("Token expirado") from exc
    except JWTError as exc:
        raise UnauthorizedError("Token inválido") from exc

    subject = claims.get("sub")
    if not subject:
        raise UnauthorizedError("Token sem 'sub'")

    return AuthenticatedIdentity(
        issuer=claims.get("iss", settings.keycloak_issuer),
        subject=subject,
        email=claims.get("email"),
        email_verified=bool(claims.get("email_verified", False)),
        name=claims.get("name"),
        preferred_username=claims.get("preferred_username"),
        raw_claims=claims,
    )


def _extract_roles_from_claim(claims: dict[str, Any], claim_path: str) -> list[str]:
    """Lê um claim de roles a partir de um caminho `a.b.c` configurável
    (ex.: `realm_access.roles` ou `resource_access.<client>.roles`)."""
    node: Any = claims
    for part in claim_path.split("."):
        if not isinstance(node, dict) or part not in node:
            return []
        node = node[part]
    if isinstance(node, list):
        return [str(item) for item in node]
    return []


async def resolve_local_user(
    session: AsyncSession, identity: AuthenticatedIdentity, settings: Settings
) -> User:
    """Vincula pelo (authProvider, externalUserId). Provisiona JIT no primeiro
    acesso com perfil VIEWER. Nunca associa automaticamente por e-mail."""
    result = await session.execute(
        select(User).where(
            User.authProvider == KEYCLOAK_AUTH_PROVIDER,
            User.externalUserId == identity.subject,
        )
    )
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    display_name = identity.name or identity.preferred_username or identity.email or identity.subject
    user = User(
        name=display_name,
        email=identity.email or f"{identity.subject}@keycloak.local",
        emailVerified=identity.email_verified,
        role=Role.VIEWER,
        active=True,
        authProvider=KEYCLOAK_AUTH_PROVIDER,
        externalUserId=identity.subject,
    )
    session.add(user)
    await session.flush()
    return user


async def _resolve_dev_user(session: AsyncSession, role: Role, settings: Settings) -> User:
    external_id = f"dev:{role.value.lower()}"
    result = await session.execute(
        select(User).where(User.authProvider == DEV_AUTH_PROVIDER, User.externalUserId == external_id)
    )
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    email_local, _, domain = settings.dev_auth_user_email.partition("@")
    email = f"{email_local}+{role.value.lower()}@{domain or 'example.com'}"
    user = User(
        name=f"Dev {role.value.title()}",
        email=email,
        emailVerified=True,
        role=role,
        active=True,
        authProvider=DEV_AUTH_PROVIDER,
        externalUserId=external_id,
    )
    session.add(user)
    await session.flush()
    return user


def _extract_bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization")
    if not header or not header.lower().startswith("bearer "):
        return None
    return header[len("bearer ") :].strip()


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    token = _extract_bearer_token(request)
    if not token:
        raise UnauthorizedError()

    if settings.dev_auth_enabled and not settings.is_production and token in _DEV_TOKEN_ROLES:
        db_user = await _resolve_dev_user(session, _DEV_TOKEN_ROLES[token], settings)
    else:
        identity = await verify_access_token(token, settings)
        db_user = await resolve_local_user(session, identity, settings)

    if not db_user.active:
        raise UnauthorizedError("Usuário inativo")

    return CurrentUser(
        id=db_user.id,
        email=db_user.email,
        name=db_user.name,
        role=Role(db_user.role.value if hasattr(db_user.role, "value") else db_user.role),
        active=db_user.active,
    )


async def require_user(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return current_user


def require_permission(permission: Permission) -> Callable[..., Awaitable[CurrentUser]]:
    async def _dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        assert_can(current_user.role, permission)
        return current_user

    return _dependency
