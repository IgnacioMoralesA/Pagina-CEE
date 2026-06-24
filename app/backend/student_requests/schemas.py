from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class RequestStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    IN_REVIEW = "IN_REVIEW"
    OBSERVED = "OBSERVED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"


class RequestPriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


def _strip_required_text(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("El campo no puede estar vacio")
    return cleaned


def _strip_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class RequestCreateRequest(BaseModel):
    title: str = Field(max_length=220)
    description: str
    category_id: UUID | None = None
    priority: RequestPriority = RequestPriority.MEDIUM

    @field_validator("title", "description")
    @classmethod
    def required_text(cls, value: str) -> str:
        return _strip_required_text(value)


class RequestUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=220)
    description: str | None = None
    category_id: UUID | None = None
    priority: RequestPriority | None = None
    assigned_to: UUID | None = None
    resolution: str | None = None

    @field_validator("title", "description")
    @classmethod
    def required_text_when_present(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required_text(value)

    @field_validator("resolution")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)


class RequestAssignRequest(BaseModel):
    assigned_to: UUID
    comment: str | None = None

    @field_validator("comment")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)


class RequestObserveRequest(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def required_text(cls, value: str) -> str:
        return _strip_required_text(value)


class RequestApproveRequest(BaseModel):
    resolution: str | None = None

    @field_validator("resolution")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)


class RequestRejectRequest(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def required_text(cls, value: str) -> str:
        return _strip_required_text(value)


class RequestCloseRequest(BaseModel):
    comment: str | None = None

    @field_validator("comment")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)


class RequestCommentCreateRequest(BaseModel):
    body: str
    is_internal: bool = False

    @field_validator("body")
    @classmethod
    def required_text(cls, value: str) -> str:
        return _strip_required_text(value)


class RequestStatusHistoryResponse(BaseModel):
    id: UUID
    request_id: UUID
    old_status: RequestStatus | None = None
    new_status: RequestStatus
    changed_by: UUID | None = None
    comment: str | None = None
    created_at: datetime


class RequestCommentResponse(BaseModel):
    id: UUID
    request_id: UUID
    author_id: UUID
    author_name: str | None = None
    body: str
    is_internal: bool
    created_at: datetime
    updated_at: datetime


class StudentRequestResponse(BaseModel):
    id: UUID
    requester_id: UUID
    requester_name: str | None = None
    category_id: UUID | None = None
    category_name: str | None = None
    category_slug: str | None = None
    title: str
    description: str
    status: RequestStatus
    priority: RequestPriority
    assigned_to: UUID | None = None
    assigned_to_name: str | None = None
    resolution: str | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    status_history: list[RequestStatusHistoryResponse] = Field(default_factory=list)
    comments: list[RequestCommentResponse] = Field(default_factory=list)


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
