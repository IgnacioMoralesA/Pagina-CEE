from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.backend.auth.dependencies import get_auth_context_validator
from app.backend.auth.jwt import create_access_token
from app.backend.auth.permissions import RoleCode
from app.backend.auth.schemas import TokenClaims, UserPrincipal
from app.backend.core.config import get_settings
from app.backend.main import create_app


class FakeAuthContextValidator:
    async def validate(self, _: str, claims: TokenClaims) -> UserPrincipal:
        return UserPrincipal(
            id=claims.user_id,
            session_id=claims.session_id,
            email="estudiante@example.edu",
            name="Estudiante Demo",
            role=RoleCode.STUDENT,
            roles=[RoleCode.STUDENT],
            permissions=["events.register", "requests.create"],
        )


def test_health_check_uses_standard_response() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Servicio disponible"
    assert payload["errors"] == []
    assert payload["data"]["status"] == "ok"
    assert payload["data"]["service"] == "CEE Conecta API"


def test_database_health_check_requires_authentication() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/health/database")

    assert response.status_code == 401
    payload = response.json()
    assert payload["data"] is None
    assert payload["message"] == "No autenticado"


def test_google_login_validation_error_uses_standard_response() -> None:
    client = TestClient(create_app())

    response = client.post("/api/v1/auth/google", json={})

    assert response.status_code == 422
    payload = response.json()
    assert payload["data"] is None
    assert payload["message"] == "Solicitud invalida"
    assert payload["errors"]
    assert payload["errors"][0]["field"] == "body.id_token"


def test_users_me_requires_bearer_token() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/users/me")

    assert response.status_code == 401
    payload = response.json()
    assert payload["data"] is None
    assert payload["message"] == "No autenticado"
    assert payload["errors"] == []


def test_users_me_returns_authenticated_principal_from_jwt() -> None:
    settings = get_settings()
    session_id = uuid4()
    token, _ = create_access_token(
        user_id=uuid4(),
        session_id=session_id,
        email="estudiante@example.edu",
        name="Estudiante Demo",
        roles=[RoleCode.STUDENT],
        permissions=["events.register", "requests.create"],
        settings=settings,
    )
    app = create_app()
    app.dependency_overrides[get_auth_context_validator] = (
        lambda: FakeAuthContextValidator()
    )
    client = TestClient(app)

    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Usuario autenticado"
    assert payload["errors"] == []
    assert payload["data"]["email"] == "estudiante@example.edu"
    assert payload["data"]["role"] == "STUDENT"
    assert payload["data"]["roles"] == ["STUDENT"]
    assert "session_id" not in payload["data"]
    assert payload["data"]["permissions"] == [
        "events.register",
        "requests.create",
    ]
