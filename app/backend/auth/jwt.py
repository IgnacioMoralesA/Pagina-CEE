from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt as pyjwt

from app.backend.auth.permissions import RoleCode, normalize_roles
from app.backend.auth.schemas import TokenClaims
from app.backend.core.config import Settings, get_settings
from app.backend.core.errors import AppError
from app.backend.core.responses import ErrorDetail


def create_access_token(
    *,
    user_id: UUID,
    session_id: UUID,
    email: str,
    name: str,
    roles: list[RoleCode] | list[str],
    permissions: list[str],
    settings: Settings | None = None,
) -> tuple[str, datetime]:
    resolved_settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=resolved_settings.jwt_access_token_minutes)
    normalized_roles = [
        role.value for role in normalize_roles([str(role) for role in roles])
    ]
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "email": email,
        "name": name,
        "roles": normalized_roles,
        "permissions": sorted(set(permissions)),
        "iat": now,
        "exp": expires_at,
    }
    token = pyjwt.encode(
        payload,
        resolved_settings.jwt_secret_key,
        algorithm=resolved_settings.jwt_algorithm,
    )
    return token, expires_at


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def decode_access_token(
    token: str,
    settings: Settings | None = None,
) -> TokenClaims:
    resolved_settings = settings or get_settings()
    try:
        payload = pyjwt.decode(
            token,
            resolved_settings.jwt_secret_key,
            algorithms=[resolved_settings.jwt_algorithm],
        )
    except pyjwt.ExpiredSignatureError as exc:
        raise AppError(
            status_code=401,
            message="Token expirado",
        ) from exc
    except pyjwt.InvalidTokenError as exc:
        raise AppError(
            status_code=401,
            message="Token invalido",
        ) from exc

    roles = normalize_roles(payload.get("roles", []))
    if not roles:
        raise AppError(
            status_code=401,
            message="Token sin roles validos",
            errors=[ErrorDetail(field="roles", detail="No hay roles reconocidos")],
        )

    try:
        user_id = UUID(str(payload["sub"]))
        session_id = UUID(str(payload["sid"]))
        email = str(payload["email"])
        name = str(payload.get("name") or email)
    except (KeyError, ValueError) as exc:
        raise AppError(
            status_code=401,
            message="Token incompleto",
        ) from exc

    permissions = [str(permission) for permission in payload.get("permissions", [])]
    return TokenClaims(
        user_id=user_id,
        session_id=session_id,
        email=email,
        name=name,
        roles=roles,
        permissions=sorted(set(permissions)),
    )
