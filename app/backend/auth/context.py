from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.audit.service import AuditAction, AuditService
from app.backend.auth.jwt import hash_token
from app.backend.auth.permissions import RoleCode, normalize_roles, select_primary_role
from app.backend.auth.schemas import TokenClaims, UserPrincipal
from app.backend.core.config import Settings, get_settings
from app.backend.core.errors import AppError
from app.backend.core.responses import ErrorDetail
from app.backend.db.session import get_session_factory


AuditFailureHook = Callable[
    [AuditAction, UUID | None, dict[str, object] | None],
    Awaitable[None],
]


@dataclass(frozen=True)
class SessionRecord:
    session_id: UUID
    user_id: UUID
    email: str
    name: str
    status: str
    expires_at: datetime
    revoked_at: datetime | None = None


class AuthContextRepository(Protocol):
    async def get_session_record(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        token_hash: str,
    ) -> SessionRecord | None:
        ...

    async def get_roles_and_permissions(
        self,
        *,
        user_id: UUID,
    ) -> tuple[list[RoleCode], list[str]]:
        ...


class DatabaseAuthContextRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_session_record(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        token_hash: str,
    ) -> SessionRecord | None:
        result = await self.db.execute(
            text(
                """
                SELECT
                    sessions.id AS session_id,
                    sessions.user_id AS user_id,
                    sessions.expires_at AS expires_at,
                    sessions.revoked_at AS revoked_at,
                    users.email AS email,
                    users.name AS name,
                    users.status AS status
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.id = :session_id
                  AND sessions.user_id = :user_id
                  AND sessions.session_token_hash = :token_hash
                  AND users.deleted_at IS NULL
                """
            ),
            {
                "session_id": session_id,
                "user_id": user_id,
                "token_hash": token_hash,
            },
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return SessionRecord(
            session_id=UUID(str(row["session_id"])),
            user_id=UUID(str(row["user_id"])),
            email=str(row["email"]),
            name=str(row["name"]),
            status=_normalize_status(row["status"]),
            expires_at=_ensure_aware(row["expires_at"]),
            revoked_at=(
                _ensure_aware(row["revoked_at"]) if row["revoked_at"] else None
            ),
        )

    async def get_roles_and_permissions(
        self,
        *,
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
                ORDER BY roles.name
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
                ORDER BY permissions.code
                """
            ),
            {"user_id": user_id},
        )
        permissions = [row["code"] for row in permissions_result.mappings()]
        return roles, permissions


class AuthContextValidator:
    def __init__(
        self,
        repository: AuthContextRepository,
        audit_failure: AuditFailureHook | None = None,
    ) -> None:
        self.repository = repository
        self.audit_failure = audit_failure

    async def validate(self, token: str, claims: TokenClaims) -> UserPrincipal:
        token_hash = hash_token(token)
        session_record = await self.repository.get_session_record(
            user_id=claims.user_id,
            session_id=claims.session_id,
            token_hash=token_hash,
        )
        if session_record is None:
            await self._audit(
                AuditAction.TOKEN_INVALID,
                claims.user_id,
                {"reason": "session_not_found"},
            )
            raise AppError(status_code=401, message="Sesion invalida")

        if session_record.revoked_at is not None:
            await self._audit(
                AuditAction.TOKEN_INVALID,
                claims.user_id,
                {"reason": "session_revoked"},
            )
            raise AppError(status_code=401, message="Sesion revocada")

        if session_record.expires_at <= datetime.now(timezone.utc):
            await self._audit(
                AuditAction.TOKEN_INVALID,
                claims.user_id,
                {"reason": "session_expired"},
            )
            raise AppError(status_code=401, message="Sesion expirada")

        if session_record.status != "ACTIVE":
            await self._audit(
                AuditAction.ACCESS_DENIED,
                claims.user_id,
                {"reason": "user_not_active"},
            )
            raise AppError(status_code=403, message="Usuario no activo")

        roles, permissions = await self.repository.get_roles_and_permissions(
            user_id=session_record.user_id
        )
        if not roles:
            await self._audit(
                AuditAction.ACCESS_DENIED,
                claims.user_id,
                {"reason": "no_active_roles"},
            )
            raise AppError(
                status_code=403,
                message="Permisos insuficientes",
                errors=[ErrorDetail(field="role", detail="Usuario sin roles activos")],
            )

        primary_role = select_primary_role([role.value for role in roles])
        return UserPrincipal(
            id=session_record.user_id,
            session_id=session_record.session_id,
            email=session_record.email,
            name=session_record.name,
            role=primary_role,
            roles=roles,
            permissions=sorted(set(permissions)),
        )

    async def _audit(
        self,
        action: AuditAction,
        actor_id: UUID | None,
        metadata: dict[str, object] | None,
    ) -> None:
        if self.audit_failure is None:
            return
        await self.audit_failure(action, actor_id, metadata)


class DatabaseAuthContextValidator:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def validate(self, token: str, claims: TokenClaims) -> UserPrincipal:
        try:
            session_factory = get_session_factory(self.settings)
            async with session_factory() as db:
                auditor = AuditService(db)

                async def audit_failure(
                    action: AuditAction,
                    actor_id: UUID | None,
                    metadata: dict[str, object] | None,
                ) -> None:
                    await auditor.record_event(
                        action=action,
                        entity_type="auth",
                        actor_id=actor_id,
                        metadata=metadata,
                    )

                validator = AuthContextValidator(
                    DatabaseAuthContextRepository(db),
                    audit_failure=audit_failure,
                )
                try:
                    principal = await validator.validate(token, claims)
                except AppError:
                    await db.commit()
                    raise
                return principal
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                status_code=503,
                message="Base de datos no disponible",
            ) from exc


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalize_status(value: object) -> str:
    return str(value).split(".")[-1].upper()
