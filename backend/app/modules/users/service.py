"""Serviço de usuários. Porte de `src/app/api/usuarios/**`.

Diferença deliberada em relação ao TS original: a criação de usuário NÃO gera
mais uma credencial local (Better Auth `accountId`/`password` hash) — a
autenticação da nova arquitetura é feita via Keycloak (ver
`app/core/auth.py`). Um usuário criado por um admin fica com
`authProvider="KEYCLOAK"` e `externalUserId=None` até o primeiro login: o
provisionamento just-in-time (`resolve_local_user`) só localiza usuários
existentes por `(authProvider, externalUserId)`, nunca por e-mail, então a
conta pré-criada só passa a ser "reivindicada" por um fluxo de vínculo
administrativo explícito — fora do escopo deste módulo. Ver resumo da tarefa
para detalhes e limitações conhecidas dessa decisão.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import KEYCLOAK_AUTH_PROVIDER, CurrentUser
from app.core.errors import ConflictError, NotFoundError
from app.core.permissions import Role as PermissionRole
from app.models.user import Role as UserRole
from app.models.user import User
from app.shared.audit import record_audit


def _to_user_role(role: PermissionRole) -> UserRole:
    return UserRole(role.value)


def _to_permission_role(role: UserRole | PermissionRole) -> PermissionRole:
    value = role.value if hasattr(role, "value") else role
    return PermissionRole(value)


async def list_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).order_by(User.createdAt.asc()))
    return list(result.scalars().all())


async def create_user(
    session: AsyncSession,
    *,
    name: str,
    email: str,
    role: PermissionRole,
    admin: CurrentUser,
) -> User:
    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("Já existe um usuário com este e-mail")

    user = User(
        name=name,
        email=email,
        role=_to_user_role(role),
        active=True,
        emailVerified=True,
        authProvider=KEYCLOAK_AUTH_PROVIDER,
        externalUserId=None,
    )
    session.add(user)
    await session.flush()

    await record_audit(
        session,
        user_id=admin.id,
        action="user.create",
        entity="User",
        entity_id=user.id,
        new_data={"email": user.email, "role": user.role.value},
    )
    await session.commit()
    await session.refresh(user)
    return user


async def update_user(
    session: AsyncSession,
    *,
    user_id: str,
    changes: dict[str, Any],
    admin: CurrentUser,
) -> User:
    target = await session.get(User, user_id)
    if target is None:
        raise NotFoundError("Usuário não encontrado")

    if target.id == admin.id:
        deactivating_self = changes.get("active") is False
        demoting_self = "role" in changes and _to_permission_role(changes["role"]) != PermissionRole.ADMIN
        if deactivating_self or demoting_self:
            # `errors.py` não expõe um erro de domínio para 400 — a rota de
            # importação já usa `HTTPException` direto para status fora da
            # taxonomia padrão (ver `app/modules/imports/router.py`, 501);
            # seguimos o mesmo precedente aqui para preservar exatamente o
            # 400 do TS original (corpo `{"detail": ...}`, não `{"error": ...}`).
            raise HTTPException(
                status_code=400,
                detail="Você não pode rebaixar ou desativar a própria conta",
            )

    previous_data = {
        "role": target.role.value,
        "active": target.active,
        "name": target.name,
    }

    new_data: dict[str, Any] = {}
    for field, value in changes.items():
        if field == "role":
            value = _to_user_role(value)
            new_data["role"] = value.value
        else:
            new_data[field] = value
        setattr(target, field, value)

    await session.flush()

    await record_audit(
        session,
        user_id=admin.id,
        action="user.update",
        entity="User",
        entity_id=target.id,
        previous_data=previous_data,
        new_data=new_data,
    )
    await session.commit()
    await session.refresh(target)
    return target
