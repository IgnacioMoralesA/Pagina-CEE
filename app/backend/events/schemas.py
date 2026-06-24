from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class EventStatus(StrEnum):
    PLANNED = "PLANNED"
    PUBLISHED = "PUBLISHED"
    FINISHED = "FINISHED"
    CANCELLED = "CANCELLED"


class RegistrationStatus(StrEnum):
    REGISTERED = "REGISTERED"
    WAITLISTED = "WAITLISTED"
    CANCELLED = "CANCELLED"


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


class EventCreateRequest(BaseModel):
    name: str = Field(max_length=220)
    description: str
    starts_at: datetime
    ends_at: datetime
    location: str | None = Field(default=None, max_length=255)
    capacity: int | None = Field(default=None, gt=0)
    category_id: UUID | None = None
    image_url: str | None = None

    @field_validator("name", "description")
    @classmethod
    def required_text(cls, value: str) -> str:
        return _strip_required_text(value)

    @field_validator("location", "image_url")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)

    @model_validator(mode="after")
    def validate_dates(self) -> "EventCreateRequest":
        if self.ends_at <= self.starts_at:
            raise ValueError("La fecha de termino debe ser posterior al inicio")
        return self


class EventUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=220)
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    location: str | None = Field(default=None, max_length=255)
    capacity: int | None = Field(default=None, gt=0)
    category_id: UUID | None = None
    image_url: str | None = None

    @field_validator("name", "description")
    @classmethod
    def required_text_when_present(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required_text(value)

    @field_validator("location", "image_url")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)

    @model_validator(mode="after")
    def validate_dates_when_complete(self) -> "EventUpdateRequest":
        if self.starts_at is not None and self.ends_at is not None:
            if self.ends_at <= self.starts_at:
                raise ValueError("La fecha de termino debe ser posterior al inicio")
        return self


class EventCancelRequest(BaseModel):
    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)


class EventAttendanceRequest(BaseModel):
    user_id: UUID
    notes: str | None = None

    @field_validator("notes")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)


class EventResponse(BaseModel):
    id: UUID
    category_id: UUID | None = None
    category_name: str | None = None
    category_slug: str | None = None
    name: str
    description: str
    starts_at: datetime
    ends_at: datetime
    location: str | None = None
    capacity: int | None = None
    registered_count: int
    responsible_id: UUID | None = None
    responsible_name: str | None = None
    status: EventStatus
    published_at: datetime | None = None
    image_url: str | None = None
    created_at: datetime
    updated_at: datetime


class EventRegistrationResponse(BaseModel):
    id: UUID
    event_id: UUID
    user_id: UUID
    status: RegistrationStatus
    registered_at: datetime
    cancelled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class EventAttendanceResponse(BaseModel):
    id: UUID
    event_id: UUID
    user_id: UUID
    checked_in_at: datetime
    checked_by: UUID | None = None
    notes: str | None = None
    created_at: datetime


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
