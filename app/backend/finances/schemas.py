from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class BudgetStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class FinancialRecordStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    VOID = "VOID"


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


class BudgetCreateRequest(BaseModel):
    student_center_id: UUID | None = None
    name: str = Field(max_length=180)
    period_start: date
    period_end: date
    total_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)

    @field_validator("name")
    @classmethod
    def required_text(cls, value: str) -> str:
        return _strip_required_text(value)

    @model_validator(mode="after")
    def validate_period(self) -> "BudgetCreateRequest":
        if self.period_end < self.period_start:
            raise ValueError("La fecha de termino no puede ser anterior al inicio")
        return self


class BudgetUpdateRequest(BaseModel):
    student_center_id: UUID | None = None
    name: str | None = Field(default=None, max_length=180)
    period_start: date | None = None
    period_end: date | None = None
    total_amount: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=2,
    )
    status: BudgetStatus | None = None

    @field_validator("name")
    @classmethod
    def required_text_when_present(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required_text(value)

    @model_validator(mode="after")
    def validate_period_when_complete(self) -> "BudgetUpdateRequest":
        required_fields = {
            "name",
            "period_start",
            "period_end",
            "total_amount",
            "status",
        }
        null_fields = [
            field
            for field in required_fields.intersection(self.model_fields_set)
            if getattr(self, field) is None
        ]
        if null_fields:
            raise ValueError(
                f"Los campos no aceptan null: {', '.join(sorted(null_fields))}"
            )
        if (
            self.period_start is not None
            and self.period_end is not None
            and self.period_end < self.period_start
        ):
            raise ValueError("La fecha de termino no puede ser anterior al inicio")
        return self


class IncomeCreateRequest(BaseModel):
    budget_id: UUID | None = None
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    source: str = Field(max_length=180)
    description: str | None = None
    received_on: date

    @field_validator("source")
    @classmethod
    def required_text(cls, value: str) -> str:
        return _strip_required_text(value)

    @field_validator("description")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)


class ExpenseCreateRequest(BaseModel):
    budget_id: UUID | None = None
    category_id: UUID | None = None
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    description: str
    spent_on: date
    receipt_document_id: UUID

    @field_validator("description")
    @classmethod
    def required_text(cls, value: str) -> str:
        return _strip_required_text(value)


class ExpenseUpdateRequest(BaseModel):
    budget_id: UUID | None = None
    category_id: UUID | None = None
    amount: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=14,
        decimal_places=2,
    )
    description: str | None = None
    spent_on: date | None = None
    receipt_document_id: UUID | None = None

    @field_validator("description")
    @classmethod
    def required_text_when_present(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required_text(value)

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "ExpenseUpdateRequest":
        required_fields = {
            "amount",
            "description",
            "spent_on",
            "receipt_document_id",
        }
        null_fields = [
            field
            for field in required_fields.intersection(self.model_fields_set)
            if getattr(self, field) is None
        ]
        if null_fields:
            raise ValueError(
                f"Los campos no aceptan null: {', '.join(sorted(null_fields))}"
            )
        return self


class BudgetResponse(BaseModel):
    id: UUID
    student_center_id: UUID | None = None
    student_center_name: str | None = None
    name: str
    period_start: date
    period_end: date
    total_amount: Decimal
    status: BudgetStatus
    created_by: UUID | None = None
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime


class IncomeResponse(BaseModel):
    id: UUID
    budget_id: UUID | None = None
    budget_name: str | None = None
    amount: Decimal
    source: str
    description: str | None = None
    received_on: date
    recorded_by: UUID | None = None
    recorded_by_name: str | None = None
    status: FinancialRecordStatus
    created_at: datetime
    updated_at: datetime


class ExpenseResponse(BaseModel):
    id: UUID
    budget_id: UUID | None = None
    budget_name: str | None = None
    category_id: UUID | None = None
    category_name: str | None = None
    category_slug: str | None = None
    amount: Decimal
    description: str
    spent_on: date
    responsible_id: UUID | None = None
    responsible_name: str | None = None
    receipt_document_id: UUID | None = None
    receipt_download_url: str
    status: FinancialRecordStatus
    created_at: datetime
    updated_at: datetime


class ExpenseCategorySummary(BaseModel):
    category_id: UUID | None = None
    category_name: str
    category_slug: str | None = None
    total: Decimal


class FinancialSummaryResponse(BaseModel):
    total_income: Decimal
    total_expenses: Decimal
    balance: Decimal
    expenses_by_category: list[ExpenseCategorySummary]


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
