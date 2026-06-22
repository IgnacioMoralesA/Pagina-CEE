from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.backend.auth.permissions import RoleCode


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(min_length=1)


class GoogleIdentity(BaseModel):
    google_sub: str
    email: str
    name: str
    avatar_url: str | None = None


class UserPrincipal(BaseModel):
    id: UUID
    session_id: UUID = Field(exclude=True)
    email: str
    name: str
    role: RoleCode
    roles: list[RoleCode]
    permissions: list[str] = Field(default_factory=list)


class TokenClaims(BaseModel):
    user_id: UUID
    session_id: UUID
    email: str
    name: str
    roles: list[RoleCode]
    permissions: list[str] = Field(default_factory=list)


class AuthenticatedUser(BaseModel):
    id: UUID
    email: str
    name: str
    role: RoleCode
    roles: list[RoleCode]
    permissions: list[str] = Field(default_factory=list)


class AuthLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: AuthenticatedUser
