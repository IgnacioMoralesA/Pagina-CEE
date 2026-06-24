from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class DocumentStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class DocumentVisibility(StrEnum):
    PUBLIC = "PUBLIC"
    AUTHENTICATED = "AUTHENTICATED"
    BOARD = "BOARD"
    PRIVATE = "PRIVATE"


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


class DocumentCreateRequest(BaseModel):
    title: str = Field(max_length=220)
    description: str | None = None
    category_id: UUID | None = None
    visibility: DocumentVisibility = DocumentVisibility.PUBLIC
    status: DocumentStatus = DocumentStatus.DRAFT

    @field_validator("title")
    @classmethod
    def required_text(cls, value: str) -> str:
        return _strip_required_text(value)

    @field_validator("description")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)


class DocumentUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=220)
    description: str | None = None
    category_id: UUID | None = None
    visibility: DocumentVisibility | None = None
    status: DocumentStatus | None = None

    @field_validator("title")
    @classmethod
    def required_text_when_present(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required_text(value)

    @field_validator("description")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)


class DocumentVersionResponse(BaseModel):
    id: UUID
    document_id: UUID
    version_number: int
    file_name: str
    mime_type: str
    file_size_bytes: int
    sha256: str | None = None
    uploaded_by: UUID | None = None
    changelog: str | None = None
    created_at: datetime
    storage_key: str = Field(exclude=True, repr=False)


class DocumentResponse(BaseModel):
    id: UUID
    category_id: UUID | None = None
    category_name: str | None = None
    category_slug: str | None = None
    title: str
    description: str | None = None
    visibility: DocumentVisibility
    status: DocumentStatus
    owner_id: UUID | None = None
    owner_name: str | None = None
    published_at: datetime | None = None
    latest_version: DocumentVersionResponse | None = None
    download_url: str | None = None
    created_at: datetime
    updated_at: datetime


class RequestAttachmentResponse(BaseModel):
    id: UUID
    request_id: UUID
    file_name: str
    mime_type: str
    file_size_bytes: int
    sha256: str | None = None
    uploaded_by: UUID | None = None
    created_at: datetime
    download_url: str
    storage_key: str = Field(exclude=True, repr=False)


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
