from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.audit.service import AuditService
from app.backend.auth.permissions import RoleCode, normalize_roles
from app.backend.auth.schemas import UserPrincipal
from app.backend.core.errors import AppError
from app.backend.users.schemas import (
    CurrentUserResponse,
    PermissionResponse,
    RoleResponse,
    UserResponse,
    UserStatus,
)


class UserRepository(Protocol):
    async def list_users(self) -> list[UserResponse]:
        ...

    async def get_user(self, user_id: UUID) -> UserResponse | None:
        ...

    async def update_user_status(
        self,
        user_id: UUID,
        status: UserStatus,
    ) -> UserResponse | None:
        ...

    async def list_roles(self) -> list[RoleResponse]:
        ...

    async def list_permissions(self) -> list[PermissionResponse]:
        ...

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...


class AdministrativeAuditor(Protocol):
    async def record_administrative_action(
        self,
        *,
        actor_id: UUID,
        entity_type: str,
        entity_id: UUID | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        ...


class DatabaseUserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_users(self) -> list[UserResponse]:
        result = await self.db.execute(
            text(
                """
                SELECT
                    id,
                    email,
                    name,
                    avatar_url,
                    status,
                    last_login_at,
                    created_at,
                    updated_at
                FROM users
                WHERE deleted_at IS NULL
                ORDER BY created_at DESC, email ASC
                """
            )
        )
        rows = [dict(row) for row in result.mappings()]
        return [await self._hydrate_user(row) for row in rows]

    async def get_user(self, user_id: UUID) -> UserResponse | None:
        result = await self.db.execute(
            text(
                """
                SELECT
                    id,
                    email,
                    name,
                    avatar_url,
                    status,
                    last_login_at,
                    created_at,
                    updated_at
                FROM users
                WHERE id = :user_id
                  AND deleted_at IS NULL
                """
            ),
            {"user_id": user_id},
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return await self._hydrate_user(dict(row))

    async def update_user_status(
        self,
        user_id: UUID,
        status: UserStatus,
    ) -> UserResponse | None:
        result = await self.db.execute(
            text(
                """
                UPDATE users
                SET status = CAST(:status AS user_status),
                    updated_at = now()
                WHERE id = :user_id
                  AND deleted_at IS NULL
                RETURNING
                    id,
                    email,
                    name,
                    avatar_url,
                    status,
                    last_login_at,
                    created_at,
                    updated_at
                """
            ),
            {"user_id": user_id, "status": status.value},
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return await self._hydrate_user(dict(row))

    async def list_roles(self) -> list[RoleResponse]:
        result = await self.db.execute(
            text(
                """
                SELECT
                    id,
                    name,
                    display_name,
                    description,
                    is_system
                FROM roles
                ORDER BY name ASC
                """
            )
        )
        roles = []
        for row in result.mappings():
            permissions = await self._load_role_permissions(UUID(str(row["id"])))
            roles.append(
                RoleResponse(
                    id=UUID(str(row["id"])),
                    name=RoleCode(str(row["name"])),
                    display_name=str(row["display_name"]),
                    description=row["description"],
                    is_system=bool(row["is_system"]),
                    permissions=permissions,
                )
            )
        return roles

    async def list_permissions(self) -> list[PermissionResponse]:
        result = await self.db.execute(
            text(
                """
                SELECT
                    id,
                    code,
                    module,
                    action,
                    description,
                    is_system
                FROM permissions
                ORDER BY module ASC, action ASC, code ASC
                """
            )
        )
        return [
            PermissionResponse(
                id=UUID(str(row["id"])),
                code=str(row["code"]),
                module=str(row["module"]),
                action=str(row["action"]),
                description=row["description"],
                is_system=bool(row["is_system"]),
            )
            for row in result.mappings()
        ]

    async def commit(self) -> None:
        await self.db.commit()

    async def rollback(self) -> None:
        await self.db.rollback()

    async def _hydrate_user(self, row: dict) -> UserResponse:
        user_id = UUID(str(row["id"]))
        roles, permissions = await self._load_user_roles_and_permissions(user_id)
        return UserResponse(
            id=user_id,
            email=str(row["email"]),
            name=str(row["name"]),
            avatar_url=row["avatar_url"],
            status=UserStatus(_normalize_status(row["status"])),
            last_login_at=row["last_login_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            roles=roles,
            permissions=permissions,
        )

    async def _load_user_roles_and_permissions(
        self,
        user_id: UUID,
    ) -> tuple[list[RoleCode], list[str]]:
        roles_result = await self.db.execute(
            text(
                """
                SELECT roles.name
                FROM roles
                JOIN user_roles ON user_roles.role_id = roles.id
                WHERE user_roles.user_id = :user_id
                  AND user_roles.deleted_at IS NULL
                ORDER BY roles.name ASC
                """
            ),
            {"user_id": user_id},
        )
        roles = normalize_roles([row["name"] for row in roles_result.mappings()])

        permissions_result = await self.db.execute(
            text(
                """
                SELECT DISTINCT permissions.code
                FROM permissions
                JOIN role_permissions ON role_permissions.permission_id = permissions.id
                JOIN user_roles ON user_roles.role_id = role_permissions.role_id
                WHERE user_roles.user_id = :user_id
                  AND user_roles.deleted_at IS NULL
                ORDER BY permissions.code ASC
                """
            ),
            {"user_id": user_id},
        )
        permissions = [str(row["code"]) for row in permissions_result.mappings()]
        return roles, permissions

    async def _load_role_permissions(self, role_id: UUID) -> list[str]:
        result = await self.db.execute(
            text(
                """
                SELECT permissions.code
                FROM permissions
                JOIN role_permissions ON role_permissions.permission_id = permissions.id
                WHERE role_permissions.role_id = :role_id
                ORDER BY permissions.code ASC
                """
            ),
            {"role_id": role_id},
        )
        return [str(row["code"]) for row in result.mappings()]


class UserService:
    def __init__(
        self,
        repository: UserRepository,
        auditor: AdministrativeAuditor | None = None,
    ) -> None:
        self.repository = repository
        self.auditor = auditor

    async def get_current_user(
        self,
        principal: UserPrincipal,
    ) -> CurrentUserResponse:
        return current_user_response_from_principal(principal)

    async def list_users(self) -> list[UserResponse]:
        return await self.repository.list_users()

    async def get_user(self, user_id: UUID) -> UserResponse:
        user = await self.repository.get_user(user_id)
        if user is None:
            raise AppError(status_code=404, message="Usuario no encontrado")
        return user

    async def update_user_status(
        self,
        *,
        actor: UserPrincipal,
        user_id: UUID,
        status: UserStatus,
    ) -> UserResponse:
        existing = await self.repository.get_user(user_id)
        if existing is None:
            raise AppError(status_code=404, message="Usuario no encontrado")

        if existing.status == status:
            return existing

        try:
            updated = await self.repository.update_user_status(user_id, status)
            if updated is None:
                raise AppError(status_code=404, message="Usuario no encontrado")

            if self.auditor is not None:
                await self.auditor.record_administrative_action(
                    actor_id=actor.id,
                    entity_type="users",
                    entity_id=user_id,
                    metadata={
                        "action": "user.status.updated",
                        "old_status": existing.status.value,
                        "new_status": updated.status.value,
                    },
                )
            await self.repository.commit()
            return updated
        except Exception:
            await self.repository.rollback()
            raise

    async def list_roles(self) -> list[RoleResponse]:
        return await self.repository.list_roles()

    async def list_permissions(self) -> list[PermissionResponse]:
        return await self.repository.list_permissions()


def create_user_service(db: AsyncSession) -> UserService:
    return UserService(DatabaseUserRepository(db), AuditService(db))


def current_user_response_from_principal(
    principal: UserPrincipal,
) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=principal.id,
        email=principal.email,
        name=principal.name,
        role=principal.role,
        roles=principal.roles,
        permissions=principal.permissions,
    )


def _normalize_status(value: object) -> str:
    return str(value).split(".")[-1].upper()
