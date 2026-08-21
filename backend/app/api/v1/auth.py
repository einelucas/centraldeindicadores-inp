"""GET /api/v1/auth/me — identidade do usuário autenticado."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, require_user
from app.core.permissions import permissions_for

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def me(current_user: CurrentUser = Depends(require_user)) -> dict:
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "role": current_user.role.value,
        "active": current_user.active,
        "permissions": [p.value for p in permissions_for(current_user.role)],
    }
