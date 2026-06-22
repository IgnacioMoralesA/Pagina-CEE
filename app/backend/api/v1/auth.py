from __future__ import annotations

from fastapi import APIRouter, Depends

from app.backend.audit.service import AuditAction, record_security_event
from app.backend.auth.google import verify_google_id_token
from app.backend.auth.schemas import AuthLoginResponse, GoogleLoginRequest
from app.backend.auth.service import AuthService
from app.backend.core.config import Settings, get_settings
from app.backend.core.errors import AppError
from app.backend.core.responses import ApiResponse, success_response
from app.backend.db.session import get_session_factory


router = APIRouter()


@router.post("/google", response_model=ApiResponse[AuthLoginResponse])
async def google_login(
    payload: GoogleLoginRequest,
    settings: Settings = Depends(get_settings),
) -> ApiResponse[AuthLoginResponse]:
    try:
        identity = await verify_google_id_token(payload.id_token, settings)
    except AppError as exc:
        await record_security_event(
            settings,
            action=AuditAction.LOGIN_FAILURE,
            metadata={"reason": exc.message},
        )
        raise

    try:
        session_factory = get_session_factory(settings)
    except Exception as exc:  # pragma: no cover - depends on local drivers.
        raise AppError(
            status_code=503,
            message="Base de datos no disponible",
        ) from exc

    async with session_factory() as db:
        service = AuthService(db, settings)
        result = await service.login_google_identity(identity)
    return success_response(result, "Login correcto")
