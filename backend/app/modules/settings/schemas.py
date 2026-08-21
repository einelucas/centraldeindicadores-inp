"""Schemas Pydantic das rotas de configurações. Porte de
`src/app/api/configuracoes/route.ts`."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.shared.schema import CamelModel

# As mesmas 8 chaves de `ACTIVE_SETTING_KEYS` (`src/app/api/configuracoes/route.ts`),
# na mesma ordem. `SettingKey` (abaixo) reaproveita esta tupla como argumento de
# `Literal` — `Literal[ACTIVE_SETTING_KEYS]` é equivalente a listar os 8
# literais diretamente, então as duas listas nunca podem divergir.
ACTIVE_SETTING_KEYS: tuple[str, ...] = (
    "rdo.target",
    "idp.target",
    "idp.excludedDisciplines",
    "idp.excludedUnits",
    "rnc.maxPrazoDias",
    "fiveS.target",
    "fiveS.excludedUnits",
    "taxa-acidentes.target",
)

SettingKey = Literal[ACTIVE_SETTING_KEYS]  # type: ignore[valid-type]


class AppSettingOut(CamelModel):
    key: str
    value: Any
    updated_at: datetime


class SettingListOut(CamelModel):
    items: list[AppSettingOut]


class UpdateSettingIn(CamelModel):
    key: SettingKey
    value: Any = Field(default=None)


class UpdateSettingOut(CamelModel):
    setting: AppSettingOut
