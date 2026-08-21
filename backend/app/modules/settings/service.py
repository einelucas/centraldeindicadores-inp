"""Serviço de configurações. Porte de `src/app/api/configuracoes/route.ts`.

A maioria das chaves grava o valor bruto em `AppSetting`, sem normalização
nem recálculo. Duas chaves são exceção real no TS original —
`idp.excludedDisciplines` e `idp.excludedUnits` — que normalizam o valor
(`parseIdpExcludedDisciplines`/`parseIdpExcludedUnits`) e recalculam
`IndicatorResult` do módulo IDP na mesma transação, porque o IDP não tem uma
rota de configuração própria (`PATCH /idp`) como RDO/5S/RNC/Taxa têm — a
única forma de alterar essas duas listas é por aqui. Isso é implementado via
`app/modules/settings/hooks.py`, ao qual o módulo IDP se registra (evita
acoplar este arquivo genérico a um módulo de indicador específico)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.models.settings import AppSetting
from app.modules.settings.hooks import get_setting_hook
from app.modules.settings.schemas import ACTIVE_SETTING_KEYS
from app.shared.audit import record_audit


async def get_active_settings(session: AsyncSession) -> list[AppSetting]:
    result = await session.execute(
        select(AppSetting).where(AppSetting.key.in_(ACTIVE_SETTING_KEYS)).order_by(AppSetting.key.asc())
    )
    return list(result.scalars().all())


async def update_setting(
    session: AsyncSession, *, key: str, value: Any, admin: CurrentUser
) -> AppSetting:
    previous = await session.get(AppSetting, key)
    previous_value = previous.value if previous is not None else None

    setting = previous
    if setting is None:
        setting = AppSetting(key=key, value=value)
        session.add(setting)
    else:
        setting.value = value
    await session.flush()

    # O hook recebe `setting` já com o valor BRUTO gravado/flushado — ele
    # normaliza `setting.value` IN PLACE e dá flush de novo antes de rodar
    # qualquer recálculo, para que o recálculo veja o valor novo (não o
    # antigo) ao reler `AppSetting` do banco.
    hook = get_setting_hook(key)
    if hook is not None:
        await hook(session, setting)

    await record_audit(
        session,
        user_id=admin.id,
        action="settings.update",
        entity="AppSetting",
        entity_id=key,
        previous_data={"value": previous_value} if previous is not None else None,
        new_data={"value": setting.value},
    )
    await session.commit()
    await session.refresh(setting)
    return setting
