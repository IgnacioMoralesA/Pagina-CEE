from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.backend.auth.dependencies import require_permissions
from app.backend.auth.permissions import PermissionCode
from app.backend.auth.schemas import UserPrincipal
from app.backend.core.config import Settings, get_settings
from app.backend.core.responses import ApiResponse, success_response
from app.backend.db.health import DatabaseHealth, check_database_connection


router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str


@router.get("/health", response_model=ApiResponse[HealthResponse])
async def health_check(
    settings: Settings = Depends(get_settings),
) -> ApiResponse[HealthResponse]:
    return success_response(
        HealthResponse(
            status="ok",
            service=settings.app_name,
            version=settings.app_version,
            environment=settings.environment,
        ),
        "Servicio disponible",
    )


@router.get("/health/database", response_model=ApiResponse[DatabaseHealth])
async def database_health_check(
    _: UserPrincipal = Depends(
        require_permissions(PermissionCode.SYSTEM_ADMIN.value)
    ),
) -> ApiResponse[DatabaseHealth]:
    database_health = await check_database_connection()
    message = (
        "Base de datos disponible"
        if database_health.status == "ok"
        else "Base de datos no disponible"
    )
    return success_response(database_health, message)
