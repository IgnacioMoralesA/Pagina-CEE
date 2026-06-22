from __future__ import annotations

import httpx

from app.backend.auth.schemas import GoogleIdentity
from app.backend.core.config import Settings, get_settings
from app.backend.core.errors import AppError
from app.backend.core.responses import ErrorDetail


GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


def _is_verified(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"true", "1", "yes"}


async def verify_google_id_token(
    id_token: str,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
) -> GoogleIdentity:
    resolved_settings = settings or get_settings()
    if not resolved_settings.google_client_id:
        raise AppError(
            status_code=503,
            message="Google OIDC no configurado",
            errors=[
                ErrorDetail(
                    field="google_client_id",
                    detail="Configure CEE_GOOGLE_CLIENT_ID",
                )
            ],
        )

    owns_client = client is None
    http_client = client or httpx.AsyncClient(
        timeout=resolved_settings.http_timeout_seconds
    )
    try:
        response = await http_client.get(
            GOOGLE_TOKENINFO_URL,
            params={"id_token": id_token},
        )
    finally:
        if owns_client:
            await http_client.aclose()

    if response.status_code != 200:
        raise AppError(status_code=401, message="Token de Google invalido")

    payload = response.json()
    if payload.get("aud") != resolved_settings.google_client_id:
        raise AppError(
            status_code=401,
            message="Token de Google con audiencia invalida",
        )

    if not _is_verified(payload.get("email_verified")):
        raise AppError(
            status_code=403,
            message="Correo de Google no verificado",
        )

    email = str(payload.get("email") or "").lower()
    if not email or "@" not in email:
        raise AppError(
            status_code=401,
            message="Token de Google sin correo valido",
        )

    domain = resolved_settings.institutional_email_domain
    if domain:
        normalized_domain = domain.lower().lstrip("@")
        if not email.endswith(f"@{normalized_domain}"):
            raise AppError(
                status_code=403,
                message="Correo no pertenece al dominio institucional",
                errors=[
                    ErrorDetail(
                        field="email",
                        detail=f"Se requiere dominio @{normalized_domain}",
                    )
                ],
            )

    google_sub = str(payload.get("sub") or "")
    if not google_sub:
        raise AppError(status_code=401, message="Token de Google sin sujeto")

    return GoogleIdentity(
        google_sub=google_sub,
        email=email,
        name=str(payload.get("name") or email.split("@")[0]),
        avatar_url=payload.get("picture"),
    )
