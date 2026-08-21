"""User, Session, Account, Verification — autenticação (tabelas legadas do
Better Auth preservadas para compatibilidade; ver app/core/auth.py para o
fluxo OIDC/Keycloak que passa a ser a fonte de autenticação)."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import Timestamp3, utcnow, uuid_pk


class Role(str, enum.Enum):
    VIEWER = "VIEWER"
    ANALYST = "ANALYST"
    ADMIN = "ADMIN"


RoleEnum = PGEnum(Role, name="Role", create_type=False)


class User(Base):
    __tablename__ = "User"

    id: Mapped[str] = uuid_pk()
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    emailVerified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    image: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[Role] = mapped_column(RoleEnum, nullable=False, default=Role.VIEWER)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    authProvider: Mapped[str] = mapped_column(String, nullable=False, default="LOCAL")
    externalUserId: Mapped[str | None] = mapped_column(String, nullable=True)
    lastLoginAt: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    sessions: Mapped[list[Session]] = relationship(back_populates="user", cascade="all,delete")
    accounts: Mapped[list[Account]] = relationship(back_populates="user", cascade="all,delete")

    __table_args__ = (
        Index("User_email_key", "email", unique=True),
        Index("User_email_idx", "email"),
        Index("User_externalUserId_idx", "externalUserId"),
    )


class Session(Base):
    __tablename__ = "Session"

    id: Mapped[str] = uuid_pk()
    userId: Mapped[str] = mapped_column(
        String, ForeignKey("User.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    token: Mapped[str] = mapped_column(String, nullable=False)
    expiresAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False)
    ipAddress: Mapped[str | None] = mapped_column(String, nullable=True)
    userAgent: Mapped[str | None] = mapped_column(String, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(back_populates="sessions")

    __table_args__ = (
        Index("Session_token_key", "token", unique=True),
        Index("Session_userId_idx", "userId"),
    )


class Account(Base):
    __tablename__ = "Account"

    id: Mapped[str] = uuid_pk()
    userId: Mapped[str] = mapped_column(
        String, ForeignKey("User.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    accountId: Mapped[str] = mapped_column(String, nullable=False)
    providerId: Mapped[str] = mapped_column(String, nullable=False)
    accessToken: Mapped[str | None] = mapped_column(String, nullable=True)
    refreshToken: Mapped[str | None] = mapped_column(String, nullable=True)
    accessTokenExpiresAt: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)
    refreshTokenExpiresAt: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)
    scope: Mapped[str | None] = mapped_column(String, nullable=True)
    idToken: Mapped[str | None] = mapped_column(String, nullable=True)
    password: Mapped[str | None] = mapped_column(String, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(back_populates="accounts")

    __table_args__ = (
        Index("Account_providerId_accountId_key", "providerId", "accountId", unique=True),
        Index("Account_userId_idx", "userId"),
    )


class Verification(Base):
    __tablename__ = "Verification"

    id: Mapped[str] = uuid_pk()
    identifier: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=False)
    expiresAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False)
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (Index("Verification_identifier_idx", "identifier"),)
