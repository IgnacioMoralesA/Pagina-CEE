from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.backend.api.router import api_router
from app.backend.core.config import Settings, get_settings, validate_runtime_security
from app.backend.core.errors import register_exception_handlers


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    validate_runtime_security(resolved_settings)
    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        openapi_url=f"{resolved_settings.api_v1_prefix}/openapi.json",
        docs_url=f"{resolved_settings.api_v1_prefix}/docs",
        redoc_url=f"{resolved_settings.api_v1_prefix}/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.dependency_overrides[get_settings] = lambda: resolved_settings
    register_exception_handlers(app)
    app.include_router(api_router, prefix=resolved_settings.api_v1_prefix)
    return app


app = create_app()
