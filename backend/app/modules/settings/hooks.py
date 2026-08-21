"""Registro de hooks por chave de `AppSetting`, disparados por
`PATCH /configuracoes`. Porte do comportamento real de
`src/app/api/configuracoes/route.ts`, que normaliza e recalcula indicadores
para chaves específicas de módulo (hoje: `idp.excludedDisciplines` e
`idp.excludedUnits` — RDO/5S/RNC/Taxa têm rotas de configuração PRÓPRIAS,
`PATCH /rdo` etc., e não passam por aqui).

Padrão idêntico ao de `app/modules/imports/registry.py`: cada módulo se
registra a partir do próprio `router.py`, no import — nunca editar este
arquivo para adicionar uma chave nele diretamente (evita acoplar o módulo
`settings`, genérico, a módulos de indicador específicos)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.models.settings import AppSetting

SettingHook = Callable[[AsyncSession, "AppSetting"], Awaitable[None]]
"""Recebe `(session, setting)` com `setting.value` já contendo o valor BRUTO
recém-gravado (e com flush já feito). O hook deve normalizar `setting.value`
IN PLACE, dar flush de novo, e só então disparar efeitos colaterais que
dependam do valor novo já estar visível em `AppSetting` (ex.: recálculo de
indicadores, que relê a configuração do banco)."""

_HOOKS: dict[str, SettingHook] = {}


def register_setting_hook(key: str, hook: SettingHook) -> None:
    _HOOKS[key] = hook


def get_setting_hook(key: str) -> SettingHook | None:
    return _HOOKS.get(key)
