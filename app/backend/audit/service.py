from __future__ import annotations

import json
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.core.config import Settings
from app.backend.db.session import get_session_factory


class AuditAction(StrEnum):
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILURE = "auth.login.failure"
    TOKEN_INVALID = "auth.token.invalid"
    ACCESS_DENIED = "auth.access.denied"
    ADMIN_ACTION = "admin.action"


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record_event(
        self,
        *,
        action: AuditAction | str,
        entity_type: str,
        actor_id: UUID | None = None,
        entity_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        await self.db.execute(
            text(
                """
                INSERT INTO audit_events (
                    actor_id,
                    action,
                    entity_type,
                    entity_id,
                    metadata,
                    ip_address,
                    user_agent
                )
                VALUES (
                    :actor_id,
                    :action,
                    :entity_type,
                    :entity_id,
                    CAST(:metadata AS jsonb),
                    CAST(:ip_address AS inet),
                    :user_agent
                )
                """
            ),
            {
                "actor_id": actor_id,
                "action": str(action),
                "entity_type": entity_type,
                "entity_id": entity_id,
                "metadata": json.dumps(metadata or {}),
                "ip_address": ip_address,
                "user_agent": user_agent,
            },
        )

    async def record_login_success(
        self,
        *,
        actor_id: UUID,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.record_event(
            action=AuditAction.LOGIN_SUCCESS,
            entity_type="auth",
            actor_id=actor_id,
            metadata=metadata,
        )

    async def record_login_failure(
        self,
        *,
        actor_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.record_event(
            action=AuditAction.LOGIN_FAILURE,
            entity_type="auth",
            actor_id=actor_id,
            metadata=metadata,
        )

    async def record_token_invalid(
        self,
        *,
        actor_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.record_event(
            action=AuditAction.TOKEN_INVALID,
            entity_type="auth",
            actor_id=actor_id,
            metadata=metadata,
        )

    async def record_access_denied(
        self,
        *,
        actor_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.record_event(
            action=AuditAction.ACCESS_DENIED,
            entity_type="auth",
            actor_id=actor_id,
            metadata=metadata,
        )

    async def record_administrative_action(
        self,
        *,
        actor_id: UUID,
        entity_type: str,
        entity_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.record_event(
            action=AuditAction.ADMIN_ACTION,
            entity_type=entity_type,
            actor_id=actor_id,
            entity_id=entity_id,
            metadata=metadata,
        )


async def record_security_event(
    settings: Settings,
    *,
    action: AuditAction,
    actor_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        session_factory = get_session_factory(settings)
        async with session_factory() as db:
            await AuditService(db).record_event(
                action=action,
                entity_type="auth",
                actor_id=actor_id,
                metadata=metadata,
            )
            await db.commit()
    except Exception:
        return
