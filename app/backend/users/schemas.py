from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

from app.backend.auth.permissions import RoleCode


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"


class UserStatusUpdateRequest(BaseModel):
    status: UserStatus


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    avatar_url: str | None = None
    status: UserStatus
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    roles: list[RoleCode]
    permissions: list[str]


class CurrentUserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    role: RoleCode
    roles: list[RoleCode]
    permissions: list[str]


class RoleResponse(BaseModel):
    id: UUID
    name: RoleCode
    display_name: str
    description: str | None = None
    is_system: bool
    permissions: list[str]


class PermissionResponse(BaseModel):
    id: UUID
    code: str
    module: str
    action: str
    description: str | None = None
    is_system: bool
