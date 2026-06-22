from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_JWT_SECRET_KEY = "dev-only-change-me"
DEVELOPMENT_ENVIRONMENTS = {"local", "dev", "development", "test", "testing"}
MINIMUM_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Runtime settings loaded from CEE_* environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="CEE_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "CEE Conecta API"
    app_version: str = "0.1.0"
    environment: str = "local"
    api_v1_prefix: str = "/api/v1"

    database_url: str = (
        "postgresql+asyncpg://cee_conecta:cee_conecta@localhost:5432/cee_conecta"
    )

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    jwt_secret_key: str = DEFAULT_JWT_SECRET_KEY
    jwt_algorithm: str = "HS256"
    jwt_access_token_minutes: int = 60

    google_client_id: str | None = None
    institutional_email_domain: str | None = None
    http_timeout_seconds: float = 5.0

    @property
    def is_development(self) -> bool:
        return self.environment.lower() in DEVELOPMENT_ENVIRONMENTS


def is_insecure_jwt_secret(secret: str | None) -> bool:
    if secret is None:
        return True
    normalized = secret.strip()
    return (
        not normalized
        or normalized == DEFAULT_JWT_SECRET_KEY
        or len(normalized) < MINIMUM_JWT_SECRET_LENGTH
    )


def validate_runtime_security(settings: Settings) -> None:
    if settings.is_development:
        return

    if is_insecure_jwt_secret(settings.jwt_secret_key):
        raise RuntimeError(
            "CEE_JWT_SECRET_KEY must be configured with a strong secret outside development"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
