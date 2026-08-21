"""Rotas de configurações — `/configuracoes`. Porte de
`src/app/api/configuracoes/route.ts`."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission
from app.modules.settings import service
from app.modules.settings.schemas import AppSettingOut, SettingListOut, UpdateSettingIn, UpdateSettingOut

router = APIRouter()


@router.get("/configuracoes", response_model=SettingListOut)
async def get_configuracoes(
    session: AsyncSession = Depends(get_session),
    # Leitura liberada a qualquer usuário autenticado (metas exibidas nos
    # painéis); a escrita exige settings:manage — ver PATCH abaixo.
    current_user: CurrentUser = Depends(require_permission(Permission.INDICATORS_READ)),
) -> SettingListOut:
    rows = await service.get_active_settings(session)
    return SettingListOut(
        items=[AppSettingOut(key=r.key, value=r.value, updated_at=r.updatedAt) for r in rows]
    )


@router.patch("/configuracoes", response_model=UpdateSettingOut)
async def patch_configuracoes(
    body: UpdateSettingIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.SETTINGS_MANAGE)),
) -> UpdateSettingOut:
    setting = await service.update_setting(session, key=body.key, value=body.value, admin=current_user)
    return UpdateSettingOut(
        setting=AppSettingOut(key=setting.key, value=setting.value, updated_at=setting.updatedAt)
    )
