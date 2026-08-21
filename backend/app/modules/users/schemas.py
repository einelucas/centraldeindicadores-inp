"""Schemas Pydantic das rotas de usuários. Porte de `src/app/api/usuarios/**`."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from app.core.permissions import Role
from app.shared.schema import CamelModel

_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class UserListItemOut(CamelModel):
    id: str
    name: str
    email: str
    role: Role
    active: bool
    auth_provider: str
    last_login_at: datetime | None
    created_at: datetime


class UserListOut(CamelModel):
    items: list[UserListItemOut]


class CreateUserIn(CamelModel):
    name: str = Field(min_length=1)
    email: str = Field(pattern=_EMAIL_PATTERN)
    role: Role = Role.VIEWER

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Nome obrigatório")
        return value


class UserBasicOut(CamelModel):
    id: str
    name: str
    email: str
    role: Role
    active: bool


class CreateUserOut(CamelModel):
    user: UserBasicOut


class UpdateUserIn(CamelModel):
    role: Role | None = None
    active: bool | None = None
    name: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _at_least_one_field(self) -> UpdateUserIn:
        if self.role is None and self.active is None and self.name is None:
            raise ValueError("Informe ao menos um campo para atualizar")
        return self


class UpdateUserOut(CamelModel):
    user: UserBasicOut
