"""Rotas de usuários — `/usuarios`. Porte de `src/app/api/usuarios/**`."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission
from app.modules.users import service
from app.modules.users.schemas import (
    CreateUserIn,
    CreateUserOut,
    UpdateUserIn,
    UpdateUserOut,
    UserBasicOut,
    UserListItemOut,
    UserListOut,
)

router = APIRouter()


@router.get("/usuarios", response_model=UserListOut)
async def list_usuarios(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.USERS_MANAGE)),
) -> UserListOut:
    users = await service.list_users(session)
    return UserListOut(
        items=[
            UserListItemOut(
                id=u.id,
                name=u.name,
                email=u.email,
                role=u.role.value,
                active=u.active,
                auth_provider=u.authProvider,
                last_login_at=u.lastLoginAt,
                created_at=u.createdAt,
            )
            for u in users
        ]
    )


@router.post("/usuarios", response_model=CreateUserOut, status_code=201)
async def create_usuario(
    body: CreateUserIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.USERS_MANAGE)),
) -> CreateUserOut:
    user = await service.create_user(
        session, name=body.name, email=body.email, role=body.role, admin=current_user
    )
    return CreateUserOut(
        user=UserBasicOut(
            id=user.id, name=user.name, email=user.email, role=user.role.value, active=user.active
        )
    )


@router.patch("/usuarios/{user_id}", response_model=UpdateUserOut)
async def update_usuario(
    user_id: str,
    body: UpdateUserIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.USERS_MANAGE)),
) -> UpdateUserOut:
    changes = body.model_dump(exclude_unset=True)
    user = await service.update_user(session, user_id=user_id, changes=changes, admin=current_user)
    return UpdateUserOut(
        user=UserBasicOut(
            id=user.id, name=user.name, email=user.email, role=user.role.value, active=user.active
        )
    )
