from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.audit.service import AuditService
from app.backend.auth.google import verify_google_id_token
from app.backend.auth.jwt import create_access_token, hash_token
from app.backend.auth.permissions import RoleCode, normalize_roles, select_primary_role
from app.backend.auth.schemas import (
    AuthenticatedUser,
    AuthLoginResponse,
    GoogleIdentity,
)
from app.backend.core.config import Settings, get_settings
from app.backend.core.errors import AppError


class AuthService:
    def __init__(
        self,
        db: AsyncSession,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()

    async def login_with_google(self, id_token: str) -> AuthLoginResponse:
        identity = await verify_google_id_token(id_token, self.settings)
        return await self.login_google_identity(identity)

    async def login_google_identity(
        self,
        identity: GoogleIdentity,
    ) -> AuthLoginResponse:
        try:
            user_row = await self._upsert_user(
                google_sub=identity.google_sub,
                email=identity.email,
                name=identity.name,
                avatar_url=identity.avatar_url,
            )
            if user_row["status"] != "ACTIVE":
                await self._record_auth_event(
                    user_id=user_row["id"],
                    email=identity.email,
                    event_type="LOGIN_FAILURE",
                    success=False,
                    error_code="USER_NOT_ACTIVE",
                )
                await AuditService(self.db).record_login_failure(
                    actor_id=user_row["id"],
                    metadata={"reason": "user_not_active"},
                )
                await self.db.commit()
                raise AppError(
                    status_code=403,
                    message="Usuario no activo",
                )

            await self._mark_last_login(user_row["id"])
            await self._ensure_student_role(user_row["id"])
            roles, permissions = await self._load_roles_and_permissions(user_row["id"])
            session_id = uuid4()
            access_token, expires_at = create_access_token(
                user_id=user_row["id"],
                session_id=session_id,
                email=user_row["email"],
                name=user_row["name"],
                roles=roles,
                permissions=permissions,
                settings=self.settings,
            )
            await self._store_session(
                session_id=session_id,
                user_id=user_row["id"],
                token=access_token,
                expires_at=expires_at,
            )
            await self._record_auth_event(
                user_id=user_row["id"],
                email=user_row["email"],
                event_type="LOGIN_SUCCESS",
                success=True,
                error_code=None,
            )
            await AuditService(self.db).record_login_success(
                actor_id=user_row["id"],
                metadata={"session_id": str(session_id)},
            )
            await self.db.commit()
        except AppError:
            raise
        except SQLAlchemyError as exc:
            await self.db.rollback()
            raise AppError(
                status_code=503,
                message="Error de base de datos durante autenticacion",
            ) from exc

        normalized_roles = normalize_roles([role.value for role in roles])
        primary_role = select_primary_role([role.value for role in normalized_roles])
        return AuthLoginResponse(
            access_token=access_token,
            expires_at=expires_at,
            user=AuthenticatedUser(
                id=user_row["id"],
                email=user_row["email"],
                name=user_row["name"],
                role=primary_role,
                roles=normalized_roles,
                permissions=permissions,
            ),
        )

    async def _upsert_user(
        self,
        *,
        google_sub: str,
        email: str,
        name: str,
        avatar_url: str | None,
    ) -> dict:
        result = await self.db.execute(
            text(
                """
                INSERT INTO users (google_sub, email, name, avatar_url)
                VALUES (:google_sub, :email, :name, :avatar_url)
                ON CONFLICT (google_sub) DO UPDATE
                SET
                    email = EXCLUDED.email,
                    name = EXCLUDED.name,
                    avatar_url = EXCLUDED.avatar_url,
                    updated_at = now()
                RETURNING id, email, name, status
                """
            ),
            {
                "google_sub": google_sub,
                "email": email,
                "name": name,
                "avatar_url": avatar_url,
            },
        )
        row = result.mappings().one()
        return {
            "id": UUID(str(row["id"])),
            "email": row["email"],
            "name": row["name"],
            "status": row["status"],
        }

    async def _mark_last_login(self, user_id: UUID) -> None:
        await self.db.execute(
            text(
                """
                UPDATE users
                SET last_login_at = now(),
                    updated_at = now()
                WHERE id = :user_id
                """
            ),
            {"user_id": user_id},
        )

    async def _ensure_student_role(self, user_id: UUID) -> None:
        await self.db.execute(
            text(
                """
                INSERT INTO user_roles (user_id, role_id)
                SELECT :user_id, roles.id
                FROM roles
                WHERE roles.name = 'STUDENT'
                ON CONFLICT (user_id, role_id) DO NOTHING
                """
            ),
            {"user_id": user_id},
        )

    async def _load_roles_and_permissions(
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
                ORDER BY roles.name
                """
            ),
            {"user_id": user_id},
        )
        roles = normalize_roles([row["name"] for row in roles_result.mappings()])
        if not roles:
            roles = [RoleCode.STUDENT]

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

    async def _store_session(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        token: str,
        expires_at: datetime,
    ) -> None:
        token_hash = hash_token(token)
        await self.db.execute(
            text(
                """
                INSERT INTO sessions (
                    id,
                    user_id,
                    provider,
                    session_token_hash,
                    expires_at,
                    started_at
                )
                VALUES (
                    :session_id,
                    :user_id,
                    'GOOGLE',
                    :token_hash,
                    :expires_at,
                    :started_at
                )
                """
            ),
            {
                "session_id": session_id,
                "user_id": user_id,
                "token_hash": token_hash,
                "expires_at": expires_at,
                "started_at": datetime.now(timezone.utc),
            },
        )

    async def _record_auth_event(
        self,
        *,
        user_id: UUID | None,
        email: str,
        event_type: str,
        success: bool,
        error_code: str | None,
    ) -> None:
        await self.db.execute(
            text(
                """
                INSERT INTO auth_events (
                    user_id,
                    email,
                    event_type,
                    provider,
                    success,
                    error_code
                )
                VALUES (
                    :user_id,
                    :email,
                    :event_type,
                    'GOOGLE',
                    :success,
                    :error_code
                )
                """
            ),
            {
                "user_id": user_id,
                "email": email,
                "event_type": event_type,
                "success": success,
                "error_code": error_code,
            },
        )
