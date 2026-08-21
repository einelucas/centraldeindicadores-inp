"""Matriz de permissões por perfil (VIEWER / ANALYST / ADMIN).

Porte literal de `src/server/permissions/index.ts` do Next.js — mesma matriz,
mesmos nomes de permissão. A autorização é sempre verificada no servidor.
"""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    VIEWER = "VIEWER"
    ANALYST = "ANALYST"
    ADMIN = "ADMIN"


class Permission(str, Enum):
    INDICATORS_READ = "indicators:read"
    INDICATORS_EXPORT = "indicators:export"
    INDICATORS_EDIT = "indicators:edit"
    INDICATORS_PUBLISH = "indicators:publish"
    IMPORT_RUN = "import:run"
    IMPORT_READ = "import:read"
    USERS_MANAGE = "users:manage"
    AUDIT_READ = "audit:read"
    SETTINGS_MANAGE = "settings:manage"


_MATRIX: dict[Role, set[Permission]] = {
    Role.VIEWER: {
        Permission.INDICATORS_READ,
        Permission.INDICATORS_EXPORT,
    },
    Role.ANALYST: {
        Permission.INDICATORS_READ,
        Permission.INDICATORS_EXPORT,
        Permission.IMPORT_RUN,
        Permission.IMPORT_READ,
    },
    Role.ADMIN: {
        Permission.INDICATORS_READ,
        Permission.INDICATORS_EXPORT,
        Permission.INDICATORS_EDIT,
        Permission.INDICATORS_PUBLISH,
        Permission.IMPORT_RUN,
        Permission.IMPORT_READ,
        Permission.USERS_MANAGE,
        Permission.AUDIT_READ,
        Permission.SETTINGS_MANAGE,
    },
}


def can(role: Role, permission: Permission) -> bool:
    return permission in _MATRIX[role]


def permissions_for(role: Role) -> list[Permission]:
    return sorted(_MATRIX[role], key=lambda p: p.value)


class ForbiddenError(Exception):
    def __init__(self, permission: Permission) -> None:
        self.permission = permission
        super().__init__(f"Permissão negada: {permission.value}")


def assert_can(role: Role, permission: Permission) -> None:
    if not can(role, permission):
        raise ForbiddenError(permission)
