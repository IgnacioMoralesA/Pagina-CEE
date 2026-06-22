from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.backend.audit.service import AuditAction, record_security_event
from app.backend.auth.context import DatabaseAuthContextValidator
from app.backend.auth.jwt import decode_access_token
from app.backend.auth.permissions import RoleCode
from app.backend.auth.schemas import UserPrincipal
from app.backend.core.config import Settings, get_settings
from app.backend.core.errors import AppError
from app.backend.core.responses import ErrorDetail


bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_context_validator(
    settings: Settings = Depends(get_settings),
) -> DatabaseAuthContextValidator:
    return DatabaseAuthContextValidator(settings)


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
    validator: DatabaseAuthContextValidator = Depends(get_auth_context_validator),
) -> UserPrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(status_code=401, message="No autenticado")

    token = credentials.credentials
    try:
        claims = decode_access_token(token, settings)
    except AppError as exc:
        await record_security_event(
            settings,
            action=AuditAction.TOKEN_INVALID,
            metadata={"reason": exc.message},
        )
        raise

    return await validator.validate(token, claims)


get_current_user = require_auth


async def optional_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
    validator: DatabaseAuthContextValidator = Depends(get_auth_context_validator),
) -> UserPrincipal | None:
    if credentials is None:
        return None

    if credentials.scheme.lower() != "bearer":
        raise AppError(status_code=401, message="No autenticado")

    token = credentials.credentials
    try:
        claims = decode_access_token(token, settings)
    except AppError as exc:
        await record_security_event(
            settings,
            action=AuditAction.TOKEN_INVALID,
            metadata={"reason": exc.message},
        )
        raise

    return await validator.validate(token, claims)


def require_roles(*required_roles: RoleCode) -> Callable[..., UserPrincipal]:
    async def checker(
        request: Request,
        current_user: UserPrincipal = Depends(require_auth),
        settings: Settings = Depends(get_settings),
    ) -> UserPrincipal:
        user_roles = set(current_user.roles)
        if RoleCode.ADMIN in user_roles or user_roles.intersection(required_roles):
            return current_user
        await record_security_event(
            settings,
            action=AuditAction.ACCESS_DENIED,
            actor_id=current_user.id,
            metadata={
                "path": request.url.path,
                "reason": "missing_role",
                "required_roles": [role.value for role in required_roles],
            },
        )
        raise AppError(
            status_code=403,
            message="Permisos insuficientes",
            errors=[ErrorDetail(field="role", detail="Rol no autorizado")],
        )

    return checker


def require_permissions(*required_permissions: str) -> Callable[..., UserPrincipal]:
    async def checker(
        request: Request,
        current_user: UserPrincipal = Depends(require_auth),
        settings: Settings = Depends(get_settings),
    ) -> UserPrincipal:
        user_permissions = set(current_user.permissions)
        if user_permissions.issuperset(required_permissions):
            return current_user
        await record_security_event(
            settings,
            action=AuditAction.ACCESS_DENIED,
            actor_id=current_user.id,
            metadata={
                "path": request.url.path,
                "reason": "missing_permission",
                "required_permissions": list(required_permissions),
            },
        )
        raise AppError(
            status_code=403,
            message="Permisos insuficientes",
            errors=[
                ErrorDetail(
                    field="permissions",
                    detail="Permiso requerido no presente",
                )
            ],
        )

    return checker
