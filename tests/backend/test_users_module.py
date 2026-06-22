from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.backend.auth.dependencies import get_auth_context_validator
from app.backend.auth.jwt import create_access_token
from app.backend.auth.permissions import PermissionCode, RoleCode
from app.backend.auth.schemas import TokenClaims, UserPrincipal
from app.backend.core.config import Settings
from app.backend.core.errors import AppError
from app.backend.main import create_app
from app.backend.users.dependencies import get_user_service
from app.backend.users.schemas import (
    CurrentUserResponse,
    PermissionResponse,
    RoleResponse,
    UserResponse,
    UserStatus,
)
from app.backend.users.service import UserService


class StaticAuthContextValidator:
    def __init__(
        self,
        *,
        roles: list[RoleCode] | None = None,
        permissions: list[str] | None = None,
        error: AppError | None = None,
    ) -> None:
        self.roles = roles or [RoleCode.STUDENT]
        self.permissions = permissions or []
        self.error = error

    async def validate(self, _: str, claims: TokenClaims) -> UserPrincipal:
        if self.error is not None:
            raise self.error
        return UserPrincipal(
            id=claims.user_id,
            session_id=claims.session_id,
            email=claims.email,
            name=claims.name,
            role=self.roles[0],
            roles=self.roles,
            permissions=self.permissions,
        )


class FakeUserService:
    def __init__(self) -> None:
        self.user_id = uuid4()
        self.updated_status: UserStatus | None = None

    async def get_current_user(
        self,
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

    async def list_users(self) -> list[UserResponse]:
        return [build_user_response(self.user_id, "admin@example.edu")]

    async def get_user(self, user_id: UUID) -> UserResponse:
        return build_user_response(user_id, "admin@example.edu")

    async def update_user_status(
        self,
        *,
        actor: UserPrincipal,
        user_id: UUID,
        status: UserStatus,
    ) -> UserResponse:
        self.updated_status = status
        return build_user_response(user_id, "admin@example.edu", status=status)

    async def list_roles(self) -> list[RoleResponse]:
        return [
            RoleResponse(
                id=uuid4(),
                name=RoleCode.ADMIN,
                display_name="Administrador",
                description="Administrador tecnico y funcional del sistema.",
                is_system=True,
                permissions=[PermissionCode.USERS_MANAGE.value],
            )
        ]

    async def list_permissions(self) -> list[PermissionResponse]:
        return [
            PermissionResponse(
                id=uuid4(),
                code=PermissionCode.USERS_MANAGE.value,
                module="users",
                action="manage",
                description="Administrar usuarios.",
                is_system=True,
            )
        ]


class FakeUserRepository:
    def __init__(self, user: UserResponse) -> None:
        self.user = user
        self.committed = False
        self.rolled_back = False

    async def list_users(self) -> list[UserResponse]:
        return [self.user]

    async def get_user(self, user_id: UUID) -> UserResponse | None:
        if user_id == self.user.id:
            return self.user
        return None

    async def update_user_status(
        self,
        user_id: UUID,
        status: UserStatus,
    ) -> UserResponse | None:
        if user_id != self.user.id:
            return None
        self.user = self.user.model_copy(update={"status": status})
        return self.user

    async def list_roles(self) -> list[RoleResponse]:
        return []

    async def list_permissions(self) -> list[PermissionResponse]:
        return []

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class RecordingAuditor:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    async def record_administrative_action(
        self,
        *,
        actor_id: UUID,
        entity_type: str,
        entity_id: UUID | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.events.append(
            {
                "actor_id": actor_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "metadata": metadata or {},
            }
        )


def build_user_response(
    user_id: UUID,
    email: str,
    *,
    status: UserStatus = UserStatus.ACTIVE,
) -> UserResponse:
    now = datetime.now(timezone.utc)
    return UserResponse(
        id=user_id,
        email=email,
        name="Usuario Demo",
        avatar_url=None,
        status=status,
        last_login_at=now,
        created_at=now,
        updated_at=now,
        roles=[RoleCode.ADMIN],
        permissions=[PermissionCode.USERS_MANAGE.value],
    )


def build_client(
    *,
    auth_validator: StaticAuthContextValidator,
    user_service: FakeUserService | None = None,
) -> tuple[TestClient, str, FakeUserService]:
    settings = Settings(jwt_secret_key="unit-test-secret")
    app = create_app(settings)
    resolved_service = user_service or FakeUserService()
    app.dependency_overrides[get_auth_context_validator] = lambda: auth_validator
    app.dependency_overrides[get_user_service] = lambda: resolved_service
    token, _ = create_access_token(
        user_id=uuid4(),
        session_id=uuid4(),
        email="admin@example.edu",
        name="Admin Demo",
        roles=[RoleCode.ADMIN],
        permissions=[],
        settings=settings,
    )
    return TestClient(app), token, resolved_service


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def assert_standard_response_shape(payload: dict[str, object]) -> None:
    assert set(payload) == {"data", "message", "errors"}


def test_authenticated_user_can_read_me() -> None:
    client, token, _ = build_client(
        auth_validator=StaticAuthContextValidator(
            roles=[RoleCode.STUDENT],
            permissions=[PermissionCode.REQUESTS_CREATE.value],
        )
    )

    response = client.get(
        "/api/v1/users/me",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Usuario autenticado"
    assert payload["data"]["email"] == "admin@example.edu"
    assert payload["data"]["role"] == "STUDENT"
    assert payload["data"]["permissions"] == [PermissionCode.REQUESTS_CREATE.value]


def test_user_without_active_session_receives_401() -> None:
    client, token, _ = build_client(
        auth_validator=StaticAuthContextValidator(
            error=AppError(status_code=401, message="Sesion invalida")
        )
    )

    response = client.get(
        "/api/v1/users/me",
        headers=auth_header(token),
    )

    assert response.status_code == 401
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["data"] is None
    assert payload["message"] == "Sesion invalida"


def test_user_without_permission_receives_403() -> None:
    client, token, _ = build_client(
        auth_validator=StaticAuthContextValidator(
            roles=[RoleCode.STUDENT],
            permissions=[PermissionCode.REQUESTS_CREATE.value],
        )
    )

    response = client.get(
        "/api/v1/users",
        headers=auth_header(token),
    )

    assert response.status_code == 403
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["data"] is None
    assert payload["message"] == "Permisos insuficientes"


def test_admin_role_without_users_manage_permission_receives_403() -> None:
    client, token, _ = build_client(
        auth_validator=StaticAuthContextValidator(
            roles=[RoleCode.ADMIN],
            permissions=[],
        )
    )

    response = client.get(
        "/api/v1/users",
        headers=auth_header(token),
    )

    assert response.status_code == 403
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Permisos insuficientes"
    assert payload["errors"][0]["field"] == "permissions"


def test_user_with_permission_can_list_users() -> None:
    client, token, _ = build_client(
        auth_validator=StaticAuthContextValidator(
            roles=[RoleCode.ADMIN],
            permissions=[PermissionCode.USERS_MANAGE.value],
        )
    )

    response = client.get(
        "/api/v1/users",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Usuarios obtenidos"
    assert payload["data"][0]["email"] == "admin@example.edu"


def test_user_with_permission_can_read_user_detail_contract() -> None:
    client, token, _ = build_client(
        auth_validator=StaticAuthContextValidator(
            roles=[RoleCode.ADMIN],
            permissions=[PermissionCode.USERS_MANAGE.value],
        )
    )
    user_id = uuid4()

    response = client.get(
        f"/api/v1/users/{user_id}",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Usuario obtenido"
    assert payload["data"]["id"] == str(user_id)
    assert payload["data"]["status"] == "ACTIVE"
    assert payload["data"]["roles"] == ["ADMIN"]
    assert payload["data"]["permissions"] == [PermissionCode.USERS_MANAGE.value]


def test_user_with_permission_can_patch_status_contract() -> None:
    client, token, user_service = build_client(
        auth_validator=StaticAuthContextValidator(
            roles=[RoleCode.ADMIN],
            permissions=[PermissionCode.USERS_MANAGE.value],
        )
    )
    user_id = uuid4()

    response = client.patch(
        f"/api/v1/users/{user_id}/status",
        headers=auth_header(token),
        json={"status": UserStatus.SUSPENDED.value},
    )

    assert response.status_code == 200
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Estado de usuario actualizado"
    assert payload["data"]["id"] == str(user_id)
    assert payload["data"]["status"] == UserStatus.SUSPENDED.value
    assert user_service.updated_status == UserStatus.SUSPENDED


def test_admin_endpoint_without_bearer_token_uses_standard_response() -> None:
    client, _, _ = build_client(
        auth_validator=StaticAuthContextValidator(
            roles=[RoleCode.ADMIN],
            permissions=[PermissionCode.USERS_MANAGE.value],
        )
    )

    response = client.get("/api/v1/users")

    assert response.status_code == 401
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["data"] is None
    assert payload["message"] == "No autenticado"
    assert payload["errors"] == []


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("/api/v1/users", "Sesion revocada"),
        ("/api/v1/roles", "Sesion expirada"),
    ],
)
def test_administrative_endpoints_reject_revoked_or_expired_session(
    path: str,
    message: str,
) -> None:
    client, token, _ = build_client(
        auth_validator=StaticAuthContextValidator(
            error=AppError(status_code=401, message=message)
        )
    )

    response = client.get(path, headers=auth_header(token))

    assert response.status_code == 401
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["data"] is None
    assert payload["message"] == message


def test_inactive_user_cannot_operate() -> None:
    client, token, _ = build_client(
        auth_validator=StaticAuthContextValidator(
            error=AppError(status_code=403, message="Usuario no activo")
        )
    )

    response = client.get(
        "/api/v1/users",
        headers=auth_header(token),
    )

    assert response.status_code == 403
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["data"] is None
    assert payload["message"] == "Usuario no activo"


def test_status_change_generates_administrative_audit() -> None:
    asyncio.run(_run_status_change_audit_check())


async def _run_status_change_audit_check() -> None:
    target_user = build_user_response(uuid4(), "target@example.edu")
    repository = FakeUserRepository(target_user)
    auditor = RecordingAuditor()
    service = UserService(repository, auditor)
    actor = UserPrincipal(
        id=uuid4(),
        session_id=uuid4(),
        email="admin@example.edu",
        name="Admin Demo",
        role=RoleCode.ADMIN,
        roles=[RoleCode.ADMIN],
        permissions=[PermissionCode.USERS_MANAGE.value],
    )

    updated = await service.update_user_status(
        actor=actor,
        user_id=target_user.id,
        status=UserStatus.SUSPENDED,
    )

    assert updated.status == UserStatus.SUSPENDED
    assert repository.committed is True
    assert repository.rolled_back is False
    assert auditor.events == [
        {
            "actor_id": actor.id,
            "entity_type": "users",
            "entity_id": target_user.id,
            "metadata": {
                "action": "user.status.updated",
                "old_status": "ACTIVE",
                "new_status": "SUSPENDED",
            },
        }
    ]


def test_roles_and_permissions_allow_roles_manage_permission() -> None:
    client, token, _ = build_client(
        auth_validator=StaticAuthContextValidator(
            roles=[RoleCode.ADMIN],
            permissions=[PermissionCode.ROLES_MANAGE.value],
        )
    )

    roles_response = client.get(
        "/api/v1/roles",
        headers=auth_header(token),
    )
    permissions_response = client.get(
        "/api/v1/permissions",
        headers=auth_header(token),
    )

    assert roles_response.status_code == 200
    roles_payload = roles_response.json()
    assert_standard_response_shape(roles_payload)
    assert roles_payload["message"] == "Roles obtenidos"
    assert roles_payload["data"][0]["name"] == "ADMIN"
    assert permissions_response.status_code == 200
    permissions_payload = permissions_response.json()
    assert_standard_response_shape(permissions_payload)
    assert permissions_payload["message"] == "Permisos obtenidos"
    assert permissions_payload["data"][0]["code"] == "users.manage"


@pytest.mark.parametrize("path", ["/api/v1/roles", "/api/v1/permissions"])
def test_roles_and_permissions_require_roles_manage_permission(path: str) -> None:
    client, token, _ = build_client(
        auth_validator=StaticAuthContextValidator(
            roles=[RoleCode.ADMIN],
            permissions=[PermissionCode.USERS_MANAGE.value],
        )
    )

    response = client.get(path, headers=auth_header(token))

    assert response.status_code == 403
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Permisos insuficientes"
    assert payload["errors"][0]["field"] == "permissions"
