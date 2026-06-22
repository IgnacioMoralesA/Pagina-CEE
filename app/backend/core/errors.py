from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.backend.core.responses import ErrorDetail, error_response


logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        message: str,
        errors: list[ErrorDetail] | None = None,
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.errors = errors or []
        super().__init__(message)


def _payload(message: str, errors: list[ErrorDetail] | None = None) -> dict:
    return error_response(message, errors).model_dump(mode="json")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(exc.message, exc.errors),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        errors = [
            ErrorDetail(
                field=".".join(str(part) for part in error["loc"]),
                detail=error["msg"],
            )
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_payload("Solicitud invalida", errors),
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "Error HTTP"
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(detail),
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled backend error")
        return JSONResponse(
            status_code=500,
            content=_payload("Error interno del servidor"),
        )
