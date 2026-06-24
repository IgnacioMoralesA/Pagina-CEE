from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.audit.service import AuditService
from app.backend.auth.permissions import PermissionCode
from app.backend.auth.schemas import UserPrincipal
from app.backend.core.errors import AppError
from app.backend.core.responses import ErrorDetail
from app.backend.finances.schemas import (
    BudgetCreateRequest,
    BudgetResponse,
    BudgetStatus,
    BudgetUpdateRequest,
    ExpenseCategorySummary,
    ExpenseCreateRequest,
    ExpenseResponse,
    ExpenseUpdateRequest,
    FinancialRecordStatus,
    FinancialSummaryResponse,
    IncomeCreateRequest,
    IncomeResponse,
    PaginatedResponse,
)


class FinanceRepository(Protocol):
    async def student_center_exists(self, student_center_id: UUID) -> bool:
        ...

    async def budget_exists(self, budget_id: UUID) -> bool:
        ...

    async def expense_category_exists(self, category_id: UUID) -> bool:
        ...

    async def receipt_document_exists(self, document_id: UUID) -> bool:
        ...

    async def list_budgets(
        self,
        *,
        public_only: bool,
        status: BudgetStatus | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[BudgetResponse]:
        ...

    async def get_budget(self, budget_id: UUID) -> BudgetResponse | None:
        ...

    async def create_budget(
        self,
        *,
        actor_id: UUID,
        payload: BudgetCreateRequest,
    ) -> BudgetResponse:
        ...

    async def update_budget(
        self,
        *,
        budget_id: UUID,
        fields: dict[str, Any],
    ) -> BudgetResponse | None:
        ...

    async def list_income(
        self,
        *,
        public_only: bool,
        status: FinancialRecordStatus | None,
        budget_id: UUID | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[IncomeResponse]:
        ...

    async def create_income(
        self,
        *,
        actor_id: UUID,
        payload: IncomeCreateRequest,
    ) -> IncomeResponse:
        ...

    async def list_expenses(
        self,
        *,
        public_only: bool,
        status: FinancialRecordStatus | None,
        budget_id: UUID | None,
        category_id: UUID | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[ExpenseResponse]:
        ...

    async def get_expense(self, expense_id: UUID) -> ExpenseResponse | None:
        ...

    async def create_expense(
        self,
        *,
        actor_id: UUID,
        payload: ExpenseCreateRequest,
        receipt_url: str,
    ) -> ExpenseResponse:
        ...

    async def update_expense(
        self,
        *,
        expense_id: UUID,
        fields: dict[str, Any],
    ) -> ExpenseResponse | None:
        ...

    async def set_expense_status(
        self,
        *,
        expense_id: UUID,
        status: FinancialRecordStatus,
    ) -> ExpenseResponse | None:
        ...

    async def get_summary(self, *, public_only: bool) -> FinancialSummaryResponse:
        ...

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...


class AdministrativeAuditor(Protocol):
    async def record_administrative_action(
        self,
        *,
        actor_id: UUID,
        entity_type: str,
        entity_id: UUID | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        ...


class DatabaseFinanceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def student_center_exists(self, student_center_id: UUID) -> bool:
        result = await self.db.execute(
            text(
                """
                SELECT 1
                FROM student_centers
                WHERE id = :student_center_id
                  AND is_active IS TRUE
                  AND deleted_at IS NULL
                """
            ),
            {"student_center_id": student_center_id},
        )
        return result.scalar_one_or_none() is not None

    async def budget_exists(self, budget_id: UUID) -> bool:
        result = await self.db.execute(
            text(
                """
                SELECT 1
                FROM budgets
                WHERE id = :budget_id
                  AND status <> 'ARCHIVED'
                  AND deleted_at IS NULL
                """
            ),
            {"budget_id": budget_id},
        )
        return result.scalar_one_or_none() is not None

    async def expense_category_exists(self, category_id: UUID) -> bool:
        result = await self.db.execute(
            text(
                """
                SELECT 1
                FROM expense_categories
                WHERE id = :category_id
                  AND is_active IS TRUE
                  AND deleted_at IS NULL
                """
            ),
            {"category_id": category_id},
        )
        return result.scalar_one_or_none() is not None

    async def receipt_document_exists(self, document_id: UUID) -> bool:
        result = await self.db.execute(
            text(
                """
                SELECT 1
                FROM documents d
                WHERE d.id = :document_id
                  AND d.status <> 'ARCHIVED'
                  AND d.deleted_at IS NULL
                  AND EXISTS (
                      SELECT 1
                      FROM document_versions dv
                      WHERE dv.document_id = d.id
                  )
                """
            ),
            {"document_id": document_id},
        )
        return result.scalar_one_or_none() is not None

    async def list_budgets(
        self,
        *,
        public_only: bool,
        status: BudgetStatus | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[BudgetResponse]:
        where_sql, params = _budget_where(public_only=public_only, status=status)
        count_result = await self.db.execute(
            text(f"SELECT count(*) FROM budgets b WHERE {where_sql}"),
            params,
        )
        result = await self.db.execute(
            text(
                f"""
                {_BUDGET_SELECT}
                WHERE {where_sql}
                ORDER BY b.period_start DESC, b.created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {**params, "limit": limit, "offset": offset},
        )
        return PaginatedResponse[BudgetResponse](
            items=[_budget_from_row(row) for row in result.mappings()],
            total=int(count_result.scalar_one()),
            limit=limit,
            offset=offset,
        )

    async def get_budget(self, budget_id: UUID) -> BudgetResponse | None:
        result = await self.db.execute(
            text(
                f"""
                {_BUDGET_SELECT}
                WHERE b.id = :budget_id
                  AND b.deleted_at IS NULL
                """
            ),
            {"budget_id": budget_id},
        )
        row = result.mappings().one_or_none()
        return _budget_from_row(row) if row is not None else None

    async def create_budget(
        self,
        *,
        actor_id: UUID,
        payload: BudgetCreateRequest,
    ) -> BudgetResponse:
        result = await self.db.execute(
            text(
                """
                INSERT INTO budgets (
                    student_center_id,
                    name,
                    period_start,
                    period_end,
                    total_amount,
                    status,
                    created_by
                )
                VALUES (
                    :student_center_id,
                    :name,
                    :period_start,
                    :period_end,
                    :total_amount,
                    'DRAFT',
                    :created_by
                )
                RETURNING id
                """
            ),
            {
                **payload.model_dump(),
                "created_by": actor_id,
            },
        )
        return await self._require_budget(UUID(str(result.scalar_one())))

    async def update_budget(
        self,
        *,
        budget_id: UUID,
        fields: dict[str, Any],
    ) -> BudgetResponse | None:
        allowed_fields = {
            "student_center_id",
            "name",
            "period_start",
            "period_end",
            "total_amount",
            "status",
        }
        assignments: list[str] = []
        params: dict[str, Any] = {"budget_id": budget_id}
        for field, raw_value in fields.items():
            if field not in allowed_fields:
                continue
            if field == "status":
                assignments.append("status = CAST(:status AS budget_status)")
            else:
                assignments.append(f"{field} = :{field}")
            params[field] = _value(raw_value)
        if not assignments:
            return await self.get_budget(budget_id)
        assignments.append("updated_at = now()")
        result = await self.db.execute(
            text(
                f"""
                UPDATE budgets
                SET {", ".join(assignments)}
                WHERE id = :budget_id
                  AND deleted_at IS NULL
                RETURNING id
                """
            ),
            params,
        )
        updated_id = result.scalar_one_or_none()
        if updated_id is None:
            return None
        return await self.get_budget(UUID(str(updated_id)))

    async def list_income(
        self,
        *,
        public_only: bool,
        status: FinancialRecordStatus | None,
        budget_id: UUID | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[IncomeResponse]:
        where_sql, params = _record_where(
            alias="i",
            public_only=public_only,
            status=status,
            budget_id=budget_id,
        )
        count_result = await self.db.execute(
            text(f"SELECT count(*) FROM income_records i WHERE {where_sql}"),
            params,
        )
        result = await self.db.execute(
            text(
                f"""
                {_INCOME_SELECT}
                WHERE {where_sql}
                ORDER BY i.received_on DESC, i.created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {**params, "limit": limit, "offset": offset},
        )
        return PaginatedResponse[IncomeResponse](
            items=[_income_from_row(row) for row in result.mappings()],
            total=int(count_result.scalar_one()),
            limit=limit,
            offset=offset,
        )

    async def create_income(
        self,
        *,
        actor_id: UUID,
        payload: IncomeCreateRequest,
    ) -> IncomeResponse:
        result = await self.db.execute(
            text(
                """
                INSERT INTO income_records (
                    budget_id,
                    amount,
                    source,
                    description,
                    received_on,
                    recorded_by,
                    status
                )
                VALUES (
                    :budget_id,
                    :amount,
                    :source,
                    :description,
                    :received_on,
                    :recorded_by,
                    'APPROVED'
                )
                RETURNING id
                """
            ),
            {
                **payload.model_dump(),
                "recorded_by": actor_id,
            },
        )
        return await self._require_income(UUID(str(result.scalar_one())))

    async def list_expenses(
        self,
        *,
        public_only: bool,
        status: FinancialRecordStatus | None,
        budget_id: UUID | None,
        category_id: UUID | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[ExpenseResponse]:
        where_sql, params = _record_where(
            alias="e",
            public_only=public_only,
            status=status,
            budget_id=budget_id,
            category_id=category_id,
        )
        count_result = await self.db.execute(
            text(f"SELECT count(*) FROM expense_records e WHERE {where_sql}"),
            params,
        )
        result = await self.db.execute(
            text(
                f"""
                {_EXPENSE_SELECT}
                WHERE {where_sql}
                ORDER BY e.spent_on DESC, e.created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {**params, "limit": limit, "offset": offset},
        )
        return PaginatedResponse[ExpenseResponse](
            items=[_expense_from_row(row) for row in result.mappings()],
            total=int(count_result.scalar_one()),
            limit=limit,
            offset=offset,
        )

    async def get_expense(self, expense_id: UUID) -> ExpenseResponse | None:
        result = await self.db.execute(
            text(
                f"""
                {_EXPENSE_SELECT}
                WHERE e.id = :expense_id
                  AND e.deleted_at IS NULL
                """
            ),
            {"expense_id": expense_id},
        )
        row = result.mappings().one_or_none()
        return _expense_from_row(row) if row is not None else None

    async def create_expense(
        self,
        *,
        actor_id: UUID,
        payload: ExpenseCreateRequest,
        receipt_url: str,
    ) -> ExpenseResponse:
        result = await self.db.execute(
            text(
                """
                INSERT INTO expense_records (
                    budget_id,
                    category_id,
                    amount,
                    description,
                    spent_on,
                    responsible_id,
                    receipt_url,
                    status
                )
                VALUES (
                    :budget_id,
                    :category_id,
                    :amount,
                    :description,
                    :spent_on,
                    :responsible_id,
                    :receipt_url,
                    'PENDING'
                )
                RETURNING id
                """
            ),
            {
                "budget_id": payload.budget_id,
                "category_id": payload.category_id,
                "amount": payload.amount,
                "description": payload.description,
                "spent_on": payload.spent_on,
                "responsible_id": actor_id,
                "receipt_url": receipt_url,
            },
        )
        return await self._require_expense(UUID(str(result.scalar_one())))

    async def update_expense(
        self,
        *,
        expense_id: UUID,
        fields: dict[str, Any],
    ) -> ExpenseResponse | None:
        allowed_fields = {
            "budget_id",
            "category_id",
            "amount",
            "description",
            "spent_on",
            "receipt_url",
        }
        assignments: list[str] = []
        params: dict[str, Any] = {"expense_id": expense_id}
        for field, raw_value in fields.items():
            if field not in allowed_fields:
                continue
            assignments.append(f"{field} = :{field}")
            params[field] = _value(raw_value)
        if not assignments:
            return await self.get_expense(expense_id)
        assignments.append("updated_at = now()")
        result = await self.db.execute(
            text(
                f"""
                UPDATE expense_records
                SET {", ".join(assignments)}
                WHERE id = :expense_id
                  AND deleted_at IS NULL
                RETURNING id
                """
            ),
            params,
        )
        updated_id = result.scalar_one_or_none()
        if updated_id is None:
            return None
        return await self.get_expense(UUID(str(updated_id)))

    async def set_expense_status(
        self,
        *,
        expense_id: UUID,
        status: FinancialRecordStatus,
    ) -> ExpenseResponse | None:
        result = await self.db.execute(
            text(
                """
                UPDATE expense_records
                SET status = CAST(:status AS financial_record_status),
                    updated_at = now()
                WHERE id = :expense_id
                  AND deleted_at IS NULL
                RETURNING id
                """
            ),
            {"expense_id": expense_id, "status": status.value},
        )
        updated_id = result.scalar_one_or_none()
        if updated_id is None:
            return None
        return await self.get_expense(UUID(str(updated_id)))

    async def get_summary(self, *, public_only: bool) -> FinancialSummaryResponse:
        record_filter = (
            "= 'APPROVED'"
            if public_only
            else "NOT IN ('REJECTED', 'VOID')"
        )
        income_result = await self.db.execute(
            text(
                f"""
                SELECT COALESCE(sum(amount), 0)
                FROM income_records
                WHERE deleted_at IS NULL
                  AND status {record_filter}
                """
            )
        )
        expense_result = await self.db.execute(
            text(
                f"""
                SELECT COALESCE(sum(amount), 0)
                FROM expense_records
                WHERE deleted_at IS NULL
                  AND status {record_filter}
                """
            )
        )
        categories_result = await self.db.execute(
            text(
                f"""
                SELECT
                    e.category_id,
                    COALESCE(c.name, 'Sin categoria') AS category_name,
                    c.slug AS category_slug,
                    COALESCE(sum(e.amount), 0) AS total
                FROM expense_records e
                LEFT JOIN expense_categories c ON c.id = e.category_id
                WHERE e.deleted_at IS NULL
                  AND e.status {record_filter}
                GROUP BY e.category_id, c.name, c.slug
                ORDER BY total DESC, category_name ASC
                """
            )
        )
        total_income = _money(income_result.scalar_one())
        total_expenses = _money(expense_result.scalar_one())
        return FinancialSummaryResponse(
            total_income=total_income,
            total_expenses=total_expenses,
            balance=total_income - total_expenses,
            expenses_by_category=[
                ExpenseCategorySummary(
                    category_id=_optional_uuid(row["category_id"]),
                    category_name=str(row["category_name"]),
                    category_slug=(
                        str(row["category_slug"]) if row["category_slug"] else None
                    ),
                    total=_money(row["total"]),
                )
                for row in categories_result.mappings()
            ],
        )

    async def commit(self) -> None:
        await self.db.commit()

    async def rollback(self) -> None:
        await self.db.rollback()

    async def _require_budget(self, budget_id: UUID) -> BudgetResponse:
        budget = await self.get_budget(budget_id)
        if budget is None:  # pragma: no cover - defensive guard.
            raise AppError(status_code=500, message="Error interno del servidor")
        return budget

    async def _require_income(self, income_id: UUID) -> IncomeResponse:
        result = await self.db.execute(
            text(
                f"""
                {_INCOME_SELECT}
                WHERE i.id = :income_id
                  AND i.deleted_at IS NULL
                """
            ),
            {"income_id": income_id},
        )
        row = result.mappings().one_or_none()
        if row is None:  # pragma: no cover - defensive guard.
            raise AppError(status_code=500, message="Error interno del servidor")
        return _income_from_row(row)

    async def _require_expense(self, expense_id: UUID) -> ExpenseResponse:
        expense = await self.get_expense(expense_id)
        if expense is None:  # pragma: no cover - defensive guard.
            raise AppError(status_code=500, message="Error interno del servidor")
        return expense


class FinanceService:
    def __init__(
        self,
        repository: FinanceRepository,
        auditor: AdministrativeAuditor | None = None,
    ) -> None:
        self.repository = repository
        self.auditor = auditor

    async def list_budgets(
        self,
        *,
        current_user: UserPrincipal | None,
        status: BudgetStatus | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[BudgetResponse]:
        is_admin = _has_finances_manage(current_user)
        if not is_admin and status not in {None, BudgetStatus.ACTIVE, BudgetStatus.CLOSED}:
            _raise_finance_access_error(current_user)
        return await self.repository.list_budgets(
            public_only=not is_admin,
            status=status,
            limit=limit,
            offset=offset,
        )

    async def get_budget(
        self,
        *,
        current_user: UserPrincipal | None,
        budget_id: UUID,
    ) -> BudgetResponse:
        budget = await self.repository.get_budget(budget_id)
        if budget is None:
            raise AppError(status_code=404, message="Presupuesto no encontrado")
        if budget.status in {BudgetStatus.ACTIVE, BudgetStatus.CLOSED}:
            return budget
        if current_user is None:
            raise AppError(status_code=404, message="Presupuesto no encontrado")
        _raise_unless_finances_manage(current_user)
        return budget

    async def create_budget(
        self,
        *,
        actor: UserPrincipal,
        payload: BudgetCreateRequest,
    ) -> BudgetResponse:
        await self._ensure_student_center(payload.student_center_id)
        try:
            budget = await self.repository.create_budget(
                actor_id=actor.id,
                payload=payload,
            )
            await self._record_admin_action(
                actor_id=actor.id,
                entity_type="budgets",
                entity_id=budget.id,
                metadata={
                    "action": "finance.budget.created",
                    "status": budget.status.value,
                },
            )
            await self.repository.commit()
            return budget
        except Exception:
            await self.repository.rollback()
            raise

    async def update_budget(
        self,
        *,
        actor: UserPrincipal,
        budget_id: UUID,
        payload: BudgetUpdateRequest,
    ) -> BudgetResponse:
        existing = await self.repository.get_budget(budget_id)
        if existing is None:
            raise AppError(status_code=404, message="Presupuesto no encontrado")
        if existing.status == BudgetStatus.ARCHIVED:
            raise AppError(status_code=409, message="Presupuesto no editable")

        fields = payload.model_dump(exclude_unset=True)
        _ensure_update_fields(fields)
        await self._ensure_student_center(fields.get("student_center_id"))
        period_start = fields.get("period_start", existing.period_start)
        period_end = fields.get("period_end", existing.period_end)
        _ensure_budget_period(period_start, period_end)
        if "status" in fields:
            _ensure_budget_transition(existing.status, fields["status"])

        try:
            updated = await self.repository.update_budget(
                budget_id=budget_id,
                fields=fields,
            )
            if updated is None:
                raise AppError(status_code=404, message="Presupuesto no encontrado")
            await self._record_admin_action(
                actor_id=actor.id,
                entity_type="budgets",
                entity_id=budget_id,
                metadata={
                    "action": "finance.budget.updated",
                    "changed_fields": sorted(fields),
                    "old_status": existing.status.value,
                    "new_status": updated.status.value,
                },
            )
            await self.repository.commit()
            return updated
        except Exception:
            await self.repository.rollback()
            raise

    async def list_income(
        self,
        *,
        current_user: UserPrincipal | None,
        status: FinancialRecordStatus | None,
        budget_id: UUID | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[IncomeResponse]:
        is_admin = _has_finances_manage(current_user)
        if not is_admin and status not in {None, FinancialRecordStatus.APPROVED}:
            _raise_finance_access_error(current_user)
        return await self.repository.list_income(
            public_only=not is_admin,
            status=status,
            budget_id=budget_id,
            limit=limit,
            offset=offset,
        )

    async def create_income(
        self,
        *,
        actor: UserPrincipal,
        payload: IncomeCreateRequest,
    ) -> IncomeResponse:
        await self._ensure_budget(payload.budget_id)
        try:
            income = await self.repository.create_income(
                actor_id=actor.id,
                payload=payload,
            )
            await self._record_admin_action(
                actor_id=actor.id,
                entity_type="income_records",
                entity_id=income.id,
                metadata={
                    "action": "finance.income.created",
                    "amount": str(income.amount),
                    "status": income.status.value,
                },
            )
            await self.repository.commit()
            return income
        except Exception:
            await self.repository.rollback()
            raise

    async def list_expenses(
        self,
        *,
        current_user: UserPrincipal | None,
        status: FinancialRecordStatus | None,
        budget_id: UUID | None,
        category_id: UUID | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[ExpenseResponse]:
        is_admin = _has_finances_manage(current_user)
        if not is_admin and status not in {None, FinancialRecordStatus.APPROVED}:
            _raise_finance_access_error(current_user)
        return await self.repository.list_expenses(
            public_only=not is_admin,
            status=status,
            budget_id=budget_id,
            category_id=category_id,
            limit=limit,
            offset=offset,
        )

    async def create_expense(
        self,
        *,
        actor: UserPrincipal,
        payload: ExpenseCreateRequest,
    ) -> ExpenseResponse:
        await self._ensure_budget(payload.budget_id)
        await self._ensure_expense_category(payload.category_id)
        await self._ensure_receipt_document(payload.receipt_document_id)
        receipt_url = _receipt_url(payload.receipt_document_id)
        try:
            expense = await self.repository.create_expense(
                actor_id=actor.id,
                payload=payload,
                receipt_url=receipt_url,
            )
            await self._record_admin_action(
                actor_id=actor.id,
                entity_type="expense_records",
                entity_id=expense.id,
                metadata={
                    "action": "finance.expense.created",
                    "amount": str(expense.amount),
                    "status": expense.status.value,
                    "receipt_document_id": str(payload.receipt_document_id),
                },
            )
            await self.repository.commit()
            return expense
        except Exception:
            await self.repository.rollback()
            raise

    async def update_expense(
        self,
        *,
        actor: UserPrincipal,
        expense_id: UUID,
        payload: ExpenseUpdateRequest,
    ) -> ExpenseResponse:
        existing = await self.repository.get_expense(expense_id)
        if existing is None:
            raise AppError(status_code=404, message="Gasto no encontrado")
        if existing.status != FinancialRecordStatus.PENDING:
            raise AppError(status_code=409, message="Gasto no editable")

        fields = payload.model_dump(exclude_unset=True)
        _ensure_update_fields(fields)
        await self._ensure_budget(fields.get("budget_id"))
        await self._ensure_expense_category(fields.get("category_id"))
        receipt_document_id = fields.pop("receipt_document_id", None)
        if receipt_document_id is not None:
            await self._ensure_receipt_document(receipt_document_id)
            fields["receipt_url"] = _receipt_url(receipt_document_id)

        try:
            updated = await self.repository.update_expense(
                expense_id=expense_id,
                fields=fields,
            )
            if updated is None:
                raise AppError(status_code=404, message="Gasto no encontrado")
            await self._record_admin_action(
                actor_id=actor.id,
                entity_type="expense_records",
                entity_id=expense_id,
                metadata={
                    "action": "finance.expense.updated",
                    "changed_fields": sorted(fields),
                },
            )
            await self.repository.commit()
            return updated
        except Exception:
            await self.repository.rollback()
            raise

    async def approve_expense(
        self,
        *,
        actor: UserPrincipal,
        expense_id: UUID,
    ) -> ExpenseResponse:
        existing = await self.repository.get_expense(expense_id)
        if existing is None:
            raise AppError(status_code=404, message="Gasto no encontrado")
        if existing.status != FinancialRecordStatus.PENDING:
            raise AppError(status_code=409, message="Gasto no aprobable")

        try:
            approved = await self.repository.set_expense_status(
                expense_id=expense_id,
                status=FinancialRecordStatus.APPROVED,
            )
            if approved is None:
                raise AppError(status_code=404, message="Gasto no encontrado")
            await self._record_admin_action(
                actor_id=actor.id,
                entity_type="expense_records",
                entity_id=expense_id,
                metadata={
                    "action": "finance.expense.approved",
                    "old_status": existing.status.value,
                    "new_status": approved.status.value,
                },
            )
            await self.repository.commit()
            return approved
        except Exception:
            await self.repository.rollback()
            raise

    async def get_summary(
        self,
        *,
        current_user: UserPrincipal | None,
    ) -> FinancialSummaryResponse:
        return await self.repository.get_summary(
            public_only=not _has_finances_manage(current_user)
        )

    async def _ensure_student_center(self, student_center_id: UUID | None) -> None:
        if student_center_id is None:
            return
        if await self.repository.student_center_exists(student_center_id):
            return
        raise _invalid_reference(
            field="student_center_id",
            message="Centro de estudiantes invalido",
        )

    async def _ensure_budget(self, budget_id: UUID | None) -> None:
        if budget_id is None:
            return
        if await self.repository.budget_exists(budget_id):
            return
        raise _invalid_reference(
            field="budget_id",
            message="Presupuesto invalido",
        )

    async def _ensure_expense_category(self, category_id: UUID | None) -> None:
        if category_id is None:
            return
        if await self.repository.expense_category_exists(category_id):
            return
        raise _invalid_reference(
            field="category_id",
            message="Categoria de gasto invalida",
        )

    async def _ensure_receipt_document(self, document_id: UUID) -> None:
        if await self.repository.receipt_document_exists(document_id):
            return
        raise _invalid_reference(
            field="receipt_document_id",
            message="Comprobante invalido",
        )

    async def _record_admin_action(
        self,
        *,
        actor_id: UUID,
        entity_type: str,
        entity_id: UUID,
        metadata: dict[str, object],
    ) -> None:
        if self.auditor is None:
            return
        await self.auditor.record_administrative_action(
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata,
        )


def create_finance_service(db: AsyncSession) -> FinanceService:
    return FinanceService(DatabaseFinanceRepository(db), AuditService(db))


def _budget_where(
    *,
    public_only: bool,
    status: BudgetStatus | None,
) -> tuple[str, dict[str, Any]]:
    conditions = ["b.deleted_at IS NULL"]
    params: dict[str, Any] = {}
    if public_only:
        conditions.append("b.status IN ('ACTIVE', 'CLOSED')")
    if status is not None:
        conditions.append("b.status = CAST(:status AS budget_status)")
        params["status"] = status.value
    return " AND ".join(conditions), params


def _record_where(
    *,
    alias: str,
    public_only: bool,
    status: FinancialRecordStatus | None,
    budget_id: UUID | None,
    category_id: UUID | None = None,
) -> tuple[str, dict[str, Any]]:
    conditions = [f"{alias}.deleted_at IS NULL"]
    params: dict[str, Any] = {}
    if public_only:
        conditions.append(f"{alias}.status = 'APPROVED'")
    if status is not None:
        conditions.append(
            f"{alias}.status = CAST(:status AS financial_record_status)"
        )
        params["status"] = status.value
    if budget_id is not None:
        conditions.append(f"{alias}.budget_id = :budget_id")
        params["budget_id"] = budget_id
    if category_id is not None:
        conditions.append(f"{alias}.category_id = :category_id")
        params["category_id"] = category_id
    return " AND ".join(conditions), params


def _has_finances_manage(current_user: UserPrincipal | None) -> bool:
    return bool(
        current_user
        and PermissionCode.FINANCES_MANAGE.value in set(current_user.permissions)
    )


def _raise_unless_finances_manage(current_user: UserPrincipal) -> None:
    if _has_finances_manage(current_user):
        return
    raise AppError(
        status_code=403,
        message="Permisos insuficientes",
        errors=[
            ErrorDetail(
                field="permissions",
                detail="Permiso requerido no presente",
            )
        ],
    )


def _raise_finance_access_error(current_user: UserPrincipal | None) -> None:
    if current_user is None:
        raise AppError(status_code=401, message="No autenticado")
    _raise_unless_finances_manage(current_user)


def _ensure_update_fields(fields: dict[str, Any]) -> None:
    if fields:
        return
    raise AppError(
        status_code=422,
        message="Solicitud invalida",
        errors=[
            ErrorDetail(
                field="body",
                detail="Debe indicar al menos un campo para actualizar",
            )
        ],
    )


def _ensure_budget_period(period_start: Any, period_end: Any) -> None:
    if period_end >= period_start:
        return
    raise AppError(
        status_code=422,
        message="Periodo de presupuesto invalido",
        errors=[
            ErrorDetail(
                field="period_end",
                detail="La fecha de termino no puede ser anterior al inicio",
            )
        ],
    )


def _ensure_budget_transition(
    current: BudgetStatus,
    requested: BudgetStatus,
) -> None:
    if requested == current:
        return
    allowed = {
        BudgetStatus.DRAFT: {BudgetStatus.ACTIVE, BudgetStatus.ARCHIVED},
        BudgetStatus.ACTIVE: {BudgetStatus.CLOSED, BudgetStatus.ARCHIVED},
        BudgetStatus.CLOSED: {BudgetStatus.ARCHIVED},
        BudgetStatus.ARCHIVED: set(),
    }
    if requested in allowed[current]:
        return
    raise AppError(status_code=409, message="Transicion de presupuesto invalida")


def _invalid_reference(*, field: str, message: str) -> AppError:
    return AppError(
        status_code=422,
        message=message,
        errors=[
            ErrorDetail(
                field=field,
                detail="El recurso no existe o no esta disponible",
            )
        ],
    )


def _receipt_url(document_id: UUID) -> str:
    return f"/api/v1/documents/{document_id}/download"


def _receipt_document_id(receipt_url: object) -> UUID | None:
    value = str(receipt_url)
    prefix = "/api/v1/documents/"
    suffix = "/download"
    if not value.startswith(prefix) or not value.endswith(suffix):
        return None
    candidate = value[len(prefix) : -len(suffix)]
    try:
        return UUID(candidate)
    except ValueError:
        return None


def _value(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    return value


def _optional_uuid(value: object) -> UUID | None:
    return UUID(str(value)) if value is not None else None


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _status_value(value: object) -> str:
    return str(value).split(".")[-1].upper()


def _budget_from_row(row: Any) -> BudgetResponse:
    return BudgetResponse(
        id=UUID(str(row["id"])),
        student_center_id=_optional_uuid(row["student_center_id"]),
        student_center_name=(
            str(row["student_center_name"]) if row["student_center_name"] else None
        ),
        name=str(row["name"]),
        period_start=row["period_start"],
        period_end=row["period_end"],
        total_amount=_money(row["total_amount"]),
        status=BudgetStatus(_status_value(row["status"])),
        created_by=_optional_uuid(row["created_by"]),
        created_by_name=(
            str(row["created_by_name"]) if row["created_by_name"] else None
        ),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _income_from_row(row: Any) -> IncomeResponse:
    return IncomeResponse(
        id=UUID(str(row["id"])),
        budget_id=_optional_uuid(row["budget_id"]),
        budget_name=str(row["budget_name"]) if row["budget_name"] else None,
        amount=_money(row["amount"]),
        source=str(row["source"]),
        description=str(row["description"]) if row["description"] else None,
        received_on=row["received_on"],
        recorded_by=_optional_uuid(row["recorded_by"]),
        recorded_by_name=(
            str(row["recorded_by_name"]) if row["recorded_by_name"] else None
        ),
        status=FinancialRecordStatus(_status_value(row["status"])),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _expense_from_row(row: Any) -> ExpenseResponse:
    receipt_url = str(row["receipt_url"])
    return ExpenseResponse(
        id=UUID(str(row["id"])),
        budget_id=_optional_uuid(row["budget_id"]),
        budget_name=str(row["budget_name"]) if row["budget_name"] else None,
        category_id=_optional_uuid(row["category_id"]),
        category_name=str(row["category_name"]) if row["category_name"] else None,
        category_slug=str(row["category_slug"]) if row["category_slug"] else None,
        amount=_money(row["amount"]),
        description=str(row["description"]),
        spent_on=row["spent_on"],
        responsible_id=_optional_uuid(row["responsible_id"]),
        responsible_name=(
            str(row["responsible_name"]) if row["responsible_name"] else None
        ),
        receipt_document_id=_receipt_document_id(receipt_url),
        receipt_download_url=receipt_url,
        status=FinancialRecordStatus(_status_value(row["status"])),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


_BUDGET_SELECT = """
SELECT
    b.id,
    b.student_center_id,
    sc.name AS student_center_name,
    b.name,
    b.period_start,
    b.period_end,
    b.total_amount,
    b.status,
    b.created_by,
    creator.name AS created_by_name,
    b.created_at,
    b.updated_at
FROM budgets b
LEFT JOIN student_centers sc ON sc.id = b.student_center_id
LEFT JOIN users creator ON creator.id = b.created_by
"""


_INCOME_SELECT = """
SELECT
    i.id,
    i.budget_id,
    b.name AS budget_name,
    i.amount,
    i.source,
    i.description,
    i.received_on,
    i.recorded_by,
    recorder.name AS recorded_by_name,
    i.status,
    i.created_at,
    i.updated_at
FROM income_records i
LEFT JOIN budgets b ON b.id = i.budget_id
LEFT JOIN users recorder ON recorder.id = i.recorded_by
"""


_EXPENSE_SELECT = """
SELECT
    e.id,
    e.budget_id,
    b.name AS budget_name,
    e.category_id,
    c.name AS category_name,
    c.slug AS category_slug,
    e.amount,
    e.description,
    e.spent_on,
    e.responsible_id,
    responsible.name AS responsible_name,
    e.receipt_url,
    e.status,
    e.created_at,
    e.updated_at
FROM expense_records e
LEFT JOIN budgets b ON b.id = e.budget_id
LEFT JOIN expense_categories c ON c.id = e.category_id
LEFT JOIN users responsible ON responsible.id = e.responsible_id
"""
