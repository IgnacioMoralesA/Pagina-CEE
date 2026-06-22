from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt as pyjwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.backend.auth.context import AuthContextValidator, SessionRecord
from app.backend.auth.dependencies import (
    get_auth_context_validator,
    require_permissions,
)
from app.backend.auth.google import verify_google_id_token
from app.backend.auth.jwt import create_access_token, decode_access_token
from app.backend.auth.permissions import PermissionCode, RoleCode
from app.backend.auth.schemas import TokenClaims, UserPrincipal
from app.backend.core.config import Settings, get_settings, validate_runtime_security
from app.backend.core.errors import AppError, register_exception_handlers
from app.backend.core.responses import success_response
from app.backend.main import create_app


class FakeGoogleResponse:
    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, object]:
        return self._payload


class FakeGoogleClient:
    def __init__(self, response: FakeGoogleResponse) -> None:
        self.response = response
        self.requested_params: dict[str, str] | None = None

    async def get(self, _: str, params: dict[str, str]) -> FakeGoogleResponse:
        self.requested_params = params
        return self.response


class FakeAuthContextValidator:
    def __init__(
        self,
        *,
        roles: list[RoleCode],
        permissions: list[str],
    ) -> None:
        self.roles = roles
        self.permissions = permissions

    async def validate(self, _: str, claims: TokenClaims) -> UserPrincipal:
        return UserPrincipal(
            id=claims.user_id,
            session_id=claims.session_id,
            email=claims.email,
            name=claims.name,
            role=self.roles[0],
            roles=self.roles,
            permissions=self.permissions,
        )


class FakeAuthRepository:
    def __init__(
        self,
        *,
        session_record: SessionRecord | None,
        roles: list[RoleCode],
        permissions: list[str],
    ) -> None:
        self.session_record = session_record
        self.roles = roles
        self.permissions = permissions

    async def get_session_record(self, **_: object) -> SessionRecord | None:
        return self.session_record

    async def get_roles_and_permissions(
        self,
        **_: object,
    ) -> tuple[list[RoleCode], list[str]]:
        return self.roles, self.permissions


def build_session_record(
    *,
    user_id,
    session_id,
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
    status: str = "ACTIVE",
) -> SessionRecord:
    return SessionRecord(
        session_id=session_id,
        user_id=user_id,
        email="estudiante@example.edu",
        name="Estudiante Demo",
        status=status,
        expires_at=expires_at or datetime.now(timezone.utc) + timedelta(hours=1),
        revoked_at=revoked_at,
    )


def test_google_oidc_accepts_verified_institutional_identity_without_network() -> None:
    settings = Settings(
        google_client_id="google-client-id",
        institutional_email_domain="example.edu",
    )
    client = FakeGoogleClient(
        FakeGoogleResponse(
            200,
            {
                "aud": "google-client-id",
                "email_verified": "true",
                "email": "estudiante@example.edu",
                "name": "Estudiante Demo",
                "picture": "https://example.edu/avatar.png",
                "sub": "google-sub-1",
            },
        )
    )

    identity = asyncio.run(
        verify_google_id_token("id-token", settings=settings, client=client)
    )

    assert client.requested_params == {"id_token": "id-token"}
    assert identity.google_sub == "google-sub-1"
    assert identity.email == "estudiante@example.edu"
    assert identity.name == "Estudiante Demo"


def test_google_oidc_rejects_non_institutional_domain_without_network() -> None:
    settings = Settings(
        google_client_id="google-client-id",
        institutional_email_domain="example.edu",
    )
    client = FakeGoogleClient(
        FakeGoogleResponse(
            200,
            {
                "aud": "google-client-id",
                "email_verified": True,
                "email": "intruso@external.test",
                "name": "Intruso",
                "sub": "google-sub-2",
            },
        )
    )

    with pytest.raises(AppError) as exc_info:
        asyncio.run(
            verify_google_id_token("id-token", settings=settings, client=client)
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.message == "Correo no pertenece al dominio institucional"


def test_decode_access_token_rejects_expired_jwt() -> None:
    settings = Settings(jwt_secret_key="unit-test-secret")
    now = datetime.now(timezone.utc)
    token = pyjwt.encode(
        {
            "sub": str(uuid4()),
            "sid": str(uuid4()),
            "email": "estudiante@example.edu",
            "name": "Estudiante Demo",
            "roles": ["STUDENT"],
            "permissions": ["requests.create"],
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(minutes=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(AppError) as exc_info:
        decode_access_token(token, settings=settings)

    assert exc_info.value.status_code == 401
    assert exc_info.value.message == "Token expirado"


def test_access_token_contains_session_identifier() -> None:
    settings = Settings(jwt_secret_key="unit-test-secret")
    user_id = uuid4()
    session_id = uuid4()

    token, _ = create_access_token(
        user_id=user_id,
        session_id=session_id,
        email="estudiante@example.edu",
        name="Estudiante Demo",
        roles=[RoleCode.STUDENT],
        permissions=[PermissionCode.REQUESTS_CREATE.value],
        settings=settings,
    )

    claims = decode_access_token(token, settings=settings)

    assert claims.user_id == user_id
    assert claims.session_id == session_id


def test_decode_access_token_rejects_jwt_without_session_identifier() -> None:
    settings = Settings(jwt_secret_key="unit-test-secret")
    now = datetime.now(timezone.utc)
    token = pyjwt.encode(
        {
            "sub": str(uuid4()),
            "email": "estudiante@example.edu",
            "name": "Estudiante Demo",
            "roles": ["STUDENT"],
            "permissions": ["requests.create"],
            "iat": now,
            "exp": now + timedelta(minutes=10),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(AppError) as exc_info:
        decode_access_token(token, settings=settings)

    assert exc_info.value.status_code == 401
    assert exc_info.value.message == "Token incompleto"


@pytest.mark.parametrize(
    ("secret", "environment"),
    [
        ("", "production"),
        ("dev-only-change-me", "production"),
        ("too-short", "staging"),
    ],
)
def test_runtime_security_rejects_weak_jwt_secret_outside_development(
    secret: str,
    environment: str,
) -> None:
    settings = Settings(environment=environment, jwt_secret_key=secret)

    with pytest.raises(RuntimeError):
        validate_runtime_security(settings)


def test_create_app_blocks_weak_jwt_secret_outside_development() -> None:
    settings = Settings(
        environment="production",
        jwt_secret_key="dev-only-change-me",
    )

    with pytest.raises(RuntimeError):
        create_app(settings)


def test_runtime_security_allows_default_secret_in_test_environment() -> None:
    settings = Settings(environment="test", jwt_secret_key="dev-only-change-me")

    validate_runtime_security(settings)


def test_auth_context_uses_current_roles_and_permissions_not_token_claims() -> None:
    settings = Settings(jwt_secret_key="unit-test-secret")
    user_id = uuid4()
    session_id = uuid4()
    token, _ = create_access_token(
        user_id=user_id,
        session_id=session_id,
        email="estudiante@example.edu",
        name="Estudiante Demo",
        roles=[RoleCode.ADMIN],
        permissions=[PermissionCode.SYSTEM_ADMIN.value],
        settings=settings,
    )
    claims = decode_access_token(token, settings=settings)
    repository = FakeAuthRepository(
        session_record=build_session_record(
            user_id=user_id,
            session_id=session_id,
        ),
        roles=[RoleCode.STUDENT],
        permissions=[PermissionCode.REQUESTS_CREATE.value],
    )

    principal = asyncio.run(AuthContextValidator(repository).validate(token, claims))

    assert principal.role == RoleCode.STUDENT
    assert principal.roles == [RoleCode.STUDENT]
    assert principal.permissions == [PermissionCode.REQUESTS_CREATE.value]


@pytest.mark.parametrize(
    ("session_record", "roles", "expected_status", "expected_message"),
    [
        (
            None,
            [RoleCode.STUDENT],
            401,
            "Sesion invalida",
        ),
        (
            "revoked",
            [RoleCode.STUDENT],
            401,
            "Sesion revocada",
        ),
        (
            "expired",
            [RoleCode.STUDENT],
            401,
            "Sesion expirada",
        ),
        (
            "inactive",
            [RoleCode.STUDENT],
            403,
            "Usuario no activo",
        ),
        (
            "no_roles",
            [],
            403,
            "Permisos insuficientes",
        ),
    ],
)
def test_auth_context_rejects_invalid_current_session_state(
    session_record,
    roles: list[RoleCode],
    expected_status: int,
    expected_message: str,
) -> None:
    settings = Settings(jwt_secret_key="unit-test-secret")
    user_id = uuid4()
    session_id = uuid4()
    token, _ = create_access_token(
        user_id=user_id,
        session_id=session_id,
        email="estudiante@example.edu",
        name="Estudiante Demo",
        roles=[RoleCode.STUDENT],
        permissions=[PermissionCode.REQUESTS_CREATE.value],
        settings=settings,
    )
    claims = decode_access_token(token, settings=settings)
    now = datetime.now(timezone.utc)

    if session_record == "revoked":
        resolved_session = build_session_record(
            user_id=user_id,
            session_id=session_id,
            revoked_at=now,
        )
    elif session_record == "expired":
        resolved_session = build_session_record(
            user_id=user_id,
            session_id=session_id,
            expires_at=now - timedelta(minutes=1),
        )
    elif session_record == "inactive":
        resolved_session = build_session_record(
            user_id=user_id,
            session_id=session_id,
            status="SUSPENDED",
        )
    elif session_record == "no_roles":
        resolved_session = build_session_record(
            user_id=user_id,
            session_id=session_id,
        )
    else:
        resolved_session = None

    audit_events: list[tuple[str, object, object]] = []

    async def audit_failure(action, actor_id, metadata):
        audit_events.append((str(action), actor_id, metadata))

    repository = FakeAuthRepository(
        session_record=resolved_session,
        roles=roles,
        permissions=[],
    )
    validator = AuthContextValidator(repository, audit_failure=audit_failure)

    with pytest.raises(AppError) as exc_info:
        asyncio.run(validator.validate(token, claims))

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.message == expected_message
    assert audit_events


def test_permission_dependency_denies_missing_permission() -> None:
    settings = Settings(jwt_secret_key="unit-test-secret")
    app = FastAPI()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_auth_context_validator] = lambda: (
        FakeAuthContextValidator(
            roles=[RoleCode.STUDENT],
            permissions=[PermissionCode.REQUESTS_CREATE.value],
        )
    )
    register_exception_handlers(app)

    @app.get("/protected")
    async def protected(
        _=Depends(require_permissions(PermissionCode.CONTENT_PUBLISH.value)),
    ):
        return success_response({"ok": True}, "OK")

    token, _ = create_access_token(
        user_id=uuid4(),
        session_id=uuid4(),
        email="estudiante@example.edu",
        name="Estudiante Demo",
        roles=[RoleCode.STUDENT],
        permissions=[PermissionCode.REQUESTS_CREATE.value],
        settings=settings,
    )

    response = TestClient(app).get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    payload = response.json()
    assert payload["data"] is None
    assert payload["message"] == "Permisos insuficientes"
    assert payload["errors"][0]["field"] == "permissions"


def test_permission_dependency_requires_current_permission_even_for_admin() -> None:
    settings = Settings(jwt_secret_key="unit-test-secret")
    app = FastAPI()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_auth_context_validator] = lambda: (
        FakeAuthContextValidator(roles=[RoleCode.ADMIN], permissions=[])
    )
    register_exception_handlers(app)

    @app.get("/protected")
    async def protected(
        _=Depends(require_permissions(PermissionCode.CONTENT_PUBLISH.value)),
    ):
        return success_response({"ok": True}, "OK")

    token, _ = create_access_token(
        user_id=uuid4(),
        session_id=uuid4(),
        email="admin@example.edu",
        name="Admin Demo",
        roles=[RoleCode.ADMIN],
        permissions=[],
        settings=settings,
    )

    response = TestClient(app).get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["message"] == "Permisos insuficientes"


def test_permission_dependency_allows_current_permission() -> None:
    settings = Settings(jwt_secret_key="unit-test-secret")
    app = FastAPI()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_auth_context_validator] = lambda: (
        FakeAuthContextValidator(
            roles=[RoleCode.ADMIN],
            permissions=[PermissionCode.CONTENT_PUBLISH.value],
        )
    )
    register_exception_handlers(app)

    @app.get("/protected")
    async def protected(
        _=Depends(require_permissions(PermissionCode.CONTENT_PUBLISH.value)),
    ):
        return success_response({"ok": True}, "OK")

    token, _ = create_access_token(
        user_id=uuid4(),
        session_id=uuid4(),
        email="admin@example.edu",
        name="Admin Demo",
        roles=[RoleCode.ADMIN],
        permissions=[],
        settings=settings,
    )

    response = TestClient(app).get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["data"] == {"ok": True}
