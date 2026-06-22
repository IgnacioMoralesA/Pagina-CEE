from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PublicationStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


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


class NewsCreateRequest(BaseModel):
    title: str = Field(max_length=220)
    summary: str | None = None
    content: str
    category_id: UUID | None = None
    image_url: str | None = None

    @field_validator("title", "content")
    @classmethod
    def required_text(cls, value: str) -> str:
        return _strip_required_text(value)

    @field_validator("summary", "image_url")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)


class NewsUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=220)
    summary: str | None = None
    content: str | None = None
    category_id: UUID | None = None
    image_url: str | None = None

    @field_validator("title", "content")
    @classmethod
    def required_text_when_present(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required_text(value)

    @field_validator("summary", "image_url")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)


class NewsResponse(BaseModel):
    id: UUID
    title: str
    slug: str
    summary: str | None = None
    content: str
    author_id: UUID
    author_name: str | None = None
    category_id: UUID | None = None
    category_name: str | None = None
    category_slug: str | None = None
    status: PublicationStatus
    published_at: datetime | None = None
    image_url: str | None = None
    created_at: datetime
    updated_at: datetime


class AnnouncementCreateRequest(BaseModel):
    title: str = Field(max_length=220)
    summary: str | None = None
    content: str
    category_id: UUID | None = None
    priority: int = Field(default=3, ge=1, le=5)
    expires_at: datetime | None = None

    @field_validator("title", "content")
    @classmethod
    def required_text(cls, value: str) -> str:
        return _strip_required_text(value)

    @field_validator("summary")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)


class AnnouncementUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=220)
    summary: str | None = None
    content: str | None = None
    category_id: UUID | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    expires_at: datetime | None = None

    @field_validator("title", "content")
    @classmethod
    def required_text_when_present(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required_text(value)

    @field_validator("summary")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)


class AnnouncementResponse(BaseModel):
    id: UUID
    title: str
    slug: str
    summary: str | None = None
    content: str
    author_id: UUID
    author_name: str | None = None
    category_id: UUID | None = None
    category_name: str | None = None
    category_slug: str | None = None
    status: PublicationStatus
    priority: int
    published_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
