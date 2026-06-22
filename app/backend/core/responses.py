from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class ErrorDetail(BaseModel):
    field: str | None = None
    detail: str


class ApiResponse(BaseModel, Generic[T]):
    data: T | None = None
    message: str
    errors: list[ErrorDetail] = Field(default_factory=list)


def success_response(data: Any = None, message: str = "OK") -> ApiResponse[Any]:
    return ApiResponse[Any](data=data, message=message, errors=[])


def error_response(
    message: str,
    errors: list[ErrorDetail] | None = None,
) -> ApiResponse[Any]:
    return ApiResponse[Any](data=None, message=message, errors=errors or [])
