from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.backend.auth.dependencies import get_auth_context_validator
from app.backend.auth.jwt import create_access_token
from app.backend.auth.permissions import PermissionCode, RoleCode
from app.backend.auth.schemas import TokenClaims, UserPrincipal
from app.backend.core.config import Settings
from app.backend.core.errors import AppError
from app.backend.finances.dependencies import get_finance_service
from app.backend.finances.schemas import (
    BudgetCreateRequest,
    BudgetResponse,
    BudgetStatus,
    ExpenseCategorySummary,
    ExpenseCreateRequest,
    ExpenseResponse,
    FinancialRecordStatus,
    FinancialSummaryResponse,
    IncomeCreateRequest,
    IncomeResponse,
    PaginatedResponse,
)
from app.backend.finances.service import FinanceService
from app.backend.main import create_app


class StaticAuthContextValidator:
    def __init__(self, *, permissions: list[str] | None = None) -> None:
        self.permissions = permissions or []

    async def validate(self, _: str, claims: TokenClaims) -> UserPrincipal:
        return UserPrincipal(
            id=claims.user_id,
            session_id=claims.session_id,
            email=claims.email,
            name=claims.name,
            role=RoleCode.TREASURER,
            roles=[RoleCode.TREASURER],
            permissions=self.permissions,
        )


class RecordingAuditor:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    async def record_administrative_action(
        self,
        *,
        actor_id: UUID,
        entity_type: str,
        entity_id: UUID | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.events.append(
            {
                "actor_id": actor_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "metadata": metadata or {},
            }
        )


class FakeFinanceRepository:
    def __init__(
        self,
        *,
        budgets: list[BudgetResponse] | None = None,
        income: list[IncomeResponse] | None = None,
        expenses: list[ExpenseResponse] | None = None,
        student_center_exists: bool = True,
        category_exists: bool = True,
        receipt_document_ids: set[UUID] | None = None,
    ) -> None:
        self.budgets = {item.id: item for item in budgets or []}
        self.income = {item.id: item for item in income or []}
        self.expenses = {item.id: item for item in expenses or []}
        self.student_center_exists_value = student_center_exists
        self.category_exists_value = category_exists
        self.receipt_document_ids = receipt_document_ids or set()
        self.committed = False
        self.rolled_back = False

    async def student_center_exists(self, student_center_id: UUID) -> bool:
        return self.student_center_exists_value

    async def budget_exists(self, budget_id: UUID) -> bool:
        budget = self.budgets.get(budget_id)
        return bool(budget and budget.status != BudgetStatus.ARCHIVED)

    async def expense_category_exists(self, category_id: UUID) -> bool:
        return self.category_exists_value

    async def receipt_document_exists(self, document_id: UUID) -> bool:
        return document_id in self.receipt_document_ids

    async def list_budgets(
        self,
        *,
        public_only: bool,
        status: BudgetStatus | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[BudgetResponse]:
        items = [
            item
            for item in self.budgets.values()
            if (
                not public_only
                or item.status in {BudgetStatus.ACTIVE, BudgetStatus.CLOSED}
            )
            and (status is None or item.status == status)
        ]
        return _page(items, limit=limit, offset=offset)

    async def get_budget(self, budget_id: UUID) -> BudgetResponse | None:
        return self.budgets.get(budget_id)

    async def create_budget(
        self,
        *,
        actor_id: UUID,
        payload: BudgetCreateRequest,
    ) -> BudgetResponse:
        budget = build_budget(
            uuid4(),
            name=payload.name,
            status=BudgetStatus.DRAFT,
            period_start=payload.period_start,
            period_end=payload.period_end,
            total_amount=payload.total_amount,
            created_by=actor_id,
            student_center_id=payload.student_center_id,
        )
        self.budgets[budget.id] = budget
        return budget

    async def update_budget(
        self,
        *,
        budget_id: UUID,
        fields: dict[str, object],
    ) -> BudgetResponse | None:
        budget = self.budgets.get(budget_id)
        if budget is None:
            return None
        updated = budget.model_copy(update=fields)
        self.budgets[budget_id] = updated
        return updated

    async def list_income(
        self,
        *,
        public_only: bool,
        status: FinancialRecordStatus | None,
        budget_id: UUID | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[IncomeResponse]:
        items = [
            item
            for item in self.income.values()
            if (not public_only or item.status == FinancialRecordStatus.APPROVED)
            and (status is None or item.status == status)
            and (budget_id is None or item.budget_id == budget_id)
        ]
        return _page(items, limit=limit, offset=offset)

    async def create_income(
        self,
        *,
        actor_id: UUID,
        payload: IncomeCreateRequest,
    ) -> IncomeResponse:
        income = build_income(
            uuid4(),
            amount=payload.amount,
            status=FinancialRecordStatus.APPROVED,
            budget_id=payload.budget_id,
            source=payload.source,
            received_on=payload.received_on,
            recorded_by=actor_id,
        )
        self.income[income.id] = income
        return income

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
        items = [
            item
            for item in self.expenses.values()
            if (not public_only or item.status == FinancialRecordStatus.APPROVED)
            and (status is None or item.status == status)
            and (budget_id is None or item.budget_id == budget_id)
            and (category_id is None or item.category_id == category_id)
        ]
        return _page(items, limit=limit, offset=offset)

    async def get_expense(self, expense_id: UUID) -> ExpenseResponse | None:
        return self.expenses.get(expense_id)

    async def create_expense(
        self,
        *,
        actor_id: UUID,
        payload: ExpenseCreateRequest,
        receipt_url: str,
    ) -> ExpenseResponse:
        expense = build_expense(
            uuid4(),
            amount=payload.amount,
            status=FinancialRecordStatus.PENDING,
            budget_id=payload.budget_id,
            category_id=payload.category_id,
            responsible_id=actor_id,
            receipt_document_id=payload.receipt_document_id,
            description=payload.description,
            spent_on=payload.spent_on,
            receipt_download_url=receipt_url,
        )
        self.expenses[expense.id] = expense
        return expense

    async def update_expense(
        self,
        *,
        expense_id: UUID,
        fields: dict[str, object],
    ) -> ExpenseResponse | None:
        expense = self.expenses.get(expense_id)
        if expense is None:
            return None
        translated = dict(fields)
        receipt_url = translated.pop("receipt_url", None)
        if receipt_url is not None:
            translated["receipt_download_url"] = receipt_url
            translated["receipt_document_id"] = UUID(
                str(receipt_url).removeprefix("/api/v1/documents/").removesuffix(
                    "/download"
                )
            )
        updated = expense.model_copy(update=translated)
        self.expenses[expense_id] = updated
        return updated

    async def set_expense_status(
        self,
        *,
        expense_id: UUID,
        status: FinancialRecordStatus,
    ) -> ExpenseResponse | None:
        expense = self.expenses.get(expense_id)
        if expense is None:
            return None
        updated = expense.model_copy(update={"status": status})
        self.expenses[expense_id] = updated
        return updated

    async def get_summary(self, *, public_only: bool) -> FinancialSummaryResponse:
        visible_statuses = (
            {FinancialRecordStatus.APPROVED}
            if public_only
            else {FinancialRecordStatus.PENDING, FinancialRecordStatus.APPROVED}
        )
        total_income = sum(
            (
                item.amount
                for item in self.income.values()
                if item.status in visible_statuses
            ),
            Decimal("0"),
        )
        visible_expenses = [
            item for item in self.expenses.values() if item.status in visible_statuses
        ]
        total_expenses = sum(
            (item.amount for item in visible_expenses),
            Decimal("0"),
        )
        category_totals: dict[
            tuple[UUID | None, str, str | None],
            Decimal,
        ] = {}
        for item in visible_expenses:
            key = (
                item.category_id,
                item.category_name or "Sin categoria",
                item.category_slug,
            )
            category_totals[key] = category_totals.get(key, Decimal("0")) + item.amount
        return FinancialSummaryResponse(
            total_income=total_income,
            total_expenses=total_expenses,
            balance=total_income - total_expenses,
            expenses_by_category=[
                ExpenseCategorySummary(
                    category_id=category_id,
                    category_name=category_name,
                    category_slug=category_slug,
                    total=total,
                )
                for (category_id, category_name, category_slug), total in category_totals.items()
            ],
        )

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def _page(items, *, limit: int, offset: int):
    return PaginatedResponse(
        items=items[offset : offset + limit],
        total=len(items),
        limit=limit,
        offset=offset,
    )


def build_budget(
    budget_id: UUID,
    *,
    name: str = "Presupuesto anual",
    status: BudgetStatus = BudgetStatus.ACTIVE,
    period_start: date | None = None,
    period_end: date | None = None,
    total_amount: Decimal = Decimal("1000000.00"),
    created_by: UUID | None = None,
    student_center_id: UUID | None = None,
) -> BudgetResponse:
    now = datetime.now(timezone.utc)
    start = period_start or date.today()
    return BudgetResponse(
        id=budget_id,
        student_center_id=student_center_id,
        student_center_name="CEE",
        name=name,
        period_start=start,
        period_end=period_end or start + timedelta(days=365),
        total_amount=total_amount,
        status=status,
        created_by=created_by,
        created_by_name="Tesoreria",
        created_at=now,
        updated_at=now,
    )


def build_income(
    income_id: UUID,
    *,
    amount: Decimal = Decimal("1000.00"),
    status: FinancialRecordStatus = FinancialRecordStatus.APPROVED,
    budget_id: UUID | None = None,
    source: str = "Cuotas",
    received_on: date | None = None,
    recorded_by: UUID | None = None,
) -> IncomeResponse:
    now = datetime.now(timezone.utc)
    return IncomeResponse(
        id=income_id,
        budget_id=budget_id,
        budget_name="Presupuesto anual" if budget_id else None,
        amount=amount,
        source=source,
        description=None,
        received_on=received_on or date.today(),
        recorded_by=recorded_by,
        recorded_by_name="Tesoreria",
        status=status,
        created_at=now,
        updated_at=now,
    )


def build_expense(
    expense_id: UUID,
    *,
    amount: Decimal = Decimal("250.00"),
    status: FinancialRecordStatus = FinancialRecordStatus.PENDING,
    budget_id: UUID | None = None,
    category_id: UUID | None = None,
    responsible_id: UUID | None = None,
    receipt_document_id: UUID | None = None,
    description: str = "Materiales",
    spent_on: date | None = None,
    receipt_download_url: str | None = None,
) -> ExpenseResponse:
    now = datetime.now(timezone.utc)
    resolved_document_id = receipt_document_id or uuid4()
    return ExpenseResponse(
        id=expense_id,
        budget_id=budget_id,
        budget_name="Presupuesto anual" if budget_id else None,
        category_id=category_id,
        category_name="Materiales" if category_id else None,
        category_slug="materiales" if category_id else None,
        amount=amount,
        description=description,
        spent_on=spent_on or date.today(),
        responsible_id=responsible_id,
        responsible_name="Tesoreria",
        receipt_document_id=resolved_document_id,
        receipt_download_url=receipt_download_url
        or f"/api/v1/documents/{resolved_document_id}/download",
        status=status,
        created_at=now,
        updated_at=now,
    )


def build_actor() -> UserPrincipal:
    return UserPrincipal(
        id=uuid4(),
        session_id=uuid4(),
        email="tesoreria@example.edu",
        name="Tesoreria",
        role=RoleCode.TREASURER,
        roles=[RoleCode.TREASURER],
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )


def build_client(
    service: FinanceService,
    *,
    permissions: list[str] | None = None,
    user_id: UUID | None = None,
) -> tuple[TestClient, str, UUID]:
    settings = Settings(jwt_secret_key="unit-test-secret")
    resolved_user_id = user_id or uuid4()
    app = create_app(settings)
    app.dependency_overrides[get_finance_service] = lambda: service
    app.dependency_overrides[get_auth_context_validator] = lambda: (
        StaticAuthContextValidator(permissions=permissions or [])
    )
    token, _ = create_access_token(
        user_id=resolved_user_id,
        session_id=uuid4(),
        email="tesoreria@example.edu",
        name="Tesoreria",
        roles=[RoleCode.TREASURER],
        permissions=[],
        settings=settings,
    )
    return TestClient(app), token, resolved_user_id


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def assert_standard_response_shape(payload: dict[str, object]) -> None:
    assert set(payload) == {"data", "message", "errors"}


def budget_payload() -> dict[str, object]:
    return {
        "name": "Presupuesto 2026",
        "period_start": "2026-01-01",
        "period_end": "2026-12-31",
        "total_amount": "5000000.00",
    }


def income_payload(*, amount: str = "1500.00") -> dict[str, object]:
    return {
        "amount": amount,
        "source": "Aporte estudiantil",
        "received_on": "2026-06-24",
    }


def expense_payload(
    document_id: UUID,
    *,
    amount: str = "500.00",
    category_id: UUID | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "amount": amount,
        "description": "Compra de materiales",
        "spent_on": "2026-06-24",
        "receipt_document_id": str(document_id),
    }
    if category_id is not None:
        payload["category_id"] = str(category_id)
    return payload


def test_public_lists_only_visible_financial_records() -> None:
    active = build_budget(uuid4(), status=BudgetStatus.ACTIVE)
    draft = build_budget(uuid4(), status=BudgetStatus.DRAFT)
    approved_income = build_income(uuid4(), status=FinancialRecordStatus.APPROVED)
    pending_income = build_income(uuid4(), status=FinancialRecordStatus.PENDING)
    approved_expense = build_expense(
        uuid4(),
        status=FinancialRecordStatus.APPROVED,
    )
    pending_expense = build_expense(
        uuid4(),
        status=FinancialRecordStatus.PENDING,
    )
    service = FinanceService(
        FakeFinanceRepository(
            budgets=[active, draft],
            income=[approved_income, pending_income],
            expenses=[approved_expense, pending_expense],
        )
    )
    client, _, _ = build_client(service)

    budgets = client.get("/api/v1/finances/budgets")
    income = client.get("/api/v1/finances/income")
    expenses = client.get("/api/v1/finances/expenses")

    assert budgets.json()["data"]["total"] == 1
    assert income.json()["data"]["total"] == 1
    assert expenses.json()["data"]["total"] == 1
    for response in (budgets, income, expenses):
        assert response.status_code == 200
        assert_standard_response_shape(response.json())


def test_public_cannot_filter_non_public_financial_statuses() -> None:
    service = FinanceService(FakeFinanceRepository())
    client, _, _ = build_client(service)

    responses = [
        client.get("/api/v1/finances/budgets?status=DRAFT"),
        client.get("/api/v1/finances/income?status=PENDING"),
        client.get("/api/v1/finances/expenses?status=PENDING"),
    ]

    assert [response.status_code for response in responses] == [401, 401, 401]
    for response in responses:
        assert_standard_response_shape(response.json())


def test_finance_manager_can_list_all_records() -> None:
    draft = build_budget(uuid4(), status=BudgetStatus.DRAFT)
    pending_income = build_income(uuid4(), status=FinancialRecordStatus.PENDING)
    pending_expense = build_expense(
        uuid4(),
        status=FinancialRecordStatus.PENDING,
    )
    service = FinanceService(
        FakeFinanceRepository(
            budgets=[draft],
            income=[pending_income],
            expenses=[pending_expense],
        )
    )
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    responses = [
        client.get("/api/v1/finances/budgets", headers=auth_header(token)),
        client.get("/api/v1/finances/income", headers=auth_header(token)),
        client.get("/api/v1/finances/expenses", headers=auth_header(token)),
    ]

    assert [response.json()["data"]["total"] for response in responses] == [1, 1, 1]


def test_budget_detail_respects_visibility() -> None:
    draft = build_budget(uuid4(), status=BudgetStatus.DRAFT)
    service = FinanceService(FakeFinanceRepository(budgets=[draft]))
    public_client, _, _ = build_client(service)
    admin_client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    public_response = public_client.get(f"/api/v1/finances/budgets/{draft.id}")
    admin_response = admin_client.get(
        f"/api/v1/finances/budgets/{draft.id}",
        headers=auth_header(token),
    )

    assert public_response.status_code == 404
    assert admin_response.status_code == 200
    assert admin_response.json()["data"]["status"] == "DRAFT"


@pytest.mark.parametrize(
    ("method", "path", "json"),
    [
        ("post", "/api/v1/finances/budgets", budget_payload()),
        ("post", "/api/v1/finances/income", income_payload()),
        ("post", "/api/v1/finances/expenses", expense_payload(uuid4())),
        ("patch", f"/api/v1/finances/budgets/{uuid4()}", {"name": "Cambio"}),
        ("patch", f"/api/v1/finances/expenses/{uuid4()}", {"description": "Cambio"}),
        ("post", f"/api/v1/finances/expenses/{uuid4()}/approve", None),
    ],
)
def test_administrative_finance_routes_require_session(
    method: str,
    path: str,
    json: dict[str, object] | None,
) -> None:
    service = FinanceService(FakeFinanceRepository())
    client, _, _ = build_client(service)

    response = getattr(client, method)(path, json=json)

    assert response.status_code == 401
    assert_standard_response_shape(response.json())


def test_user_without_permission_cannot_create_income_or_expense() -> None:
    document_id = uuid4()
    service = FinanceService(
        FakeFinanceRepository(receipt_document_ids={document_id})
    )
    client, token, _ = build_client(service)

    income_response = client.post(
        "/api/v1/finances/income",
        headers=auth_header(token),
        json=income_payload(),
    )
    expense_response = client.post(
        "/api/v1/finances/expenses",
        headers=auth_header(token),
        json=expense_payload(document_id),
    )

    assert income_response.status_code == 403
    assert expense_response.status_code == 403
    assert_standard_response_shape(income_response.json())
    assert_standard_response_shape(expense_response.json())


def test_finance_manager_can_create_budget_and_audit() -> None:
    repository = FakeFinanceRepository()
    auditor = RecordingAuditor()
    service = FinanceService(repository, auditor)
    client, token, actor_id = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    response = client.post(
        "/api/v1/finances/budgets",
        headers=auth_header(token),
        json=budget_payload(),
    )

    assert response.status_code == 201
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["data"]["status"] == "DRAFT"
    assert repository.committed is True
    assert auditor.events == [
        {
            "actor_id": actor_id,
            "entity_type": "budgets",
            "entity_id": UUID(payload["data"]["id"]),
            "metadata": {
                "action": "finance.budget.created",
                "status": "DRAFT",
            },
        }
    ]


def test_budget_rejects_invalid_period() -> None:
    service = FinanceService(FakeFinanceRepository())
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )
    payload = budget_payload()
    payload["period_end"] = "2025-12-31"

    response = client.post(
        "/api/v1/finances/budgets",
        headers=auth_header(token),
        json=payload,
    )

    assert response.status_code == 422
    assert_standard_response_shape(response.json())


@pytest.mark.parametrize("amount", ["0", "-1"])
def test_income_rejects_non_positive_amount(amount: str) -> None:
    service = FinanceService(FakeFinanceRepository())
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    response = client.post(
        "/api/v1/finances/income",
        headers=auth_header(token),
        json=income_payload(amount=amount),
    )

    assert response.status_code == 422
    assert_standard_response_shape(response.json())


def test_finance_manager_can_create_income_and_audit() -> None:
    repository = FakeFinanceRepository()
    auditor = RecordingAuditor()
    service = FinanceService(repository, auditor)
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    response = client.post(
        "/api/v1/finances/income",
        headers=auth_header(token),
        json=income_payload(),
    )

    assert response.status_code == 201
    assert response.json()["data"]["status"] == "APPROVED"
    assert auditor.events[0]["entity_type"] == "income_records"
    assert auditor.events[0]["metadata"]["action"] == "finance.income.created"


@pytest.mark.parametrize("amount", ["0", "-1"])
def test_expense_rejects_non_positive_amount(amount: str) -> None:
    document_id = uuid4()
    service = FinanceService(
        FakeFinanceRepository(receipt_document_ids={document_id})
    )
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    response = client.post(
        "/api/v1/finances/expenses",
        headers=auth_header(token),
        json=expense_payload(document_id, amount=amount),
    )

    assert response.status_code == 422
    assert_standard_response_shape(response.json())


def test_expense_can_link_existing_document_and_audit() -> None:
    document_id = uuid4()
    repository = FakeFinanceRepository(receipt_document_ids={document_id})
    auditor = RecordingAuditor()
    service = FinanceService(repository, auditor)
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    response = client.post(
        "/api/v1/finances/expenses",
        headers=auth_header(token),
        json=expense_payload(document_id),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["data"]["status"] == "PENDING"
    assert payload["data"]["receipt_document_id"] == str(document_id)
    assert payload["data"]["receipt_download_url"] == (
        f"/api/v1/documents/{document_id}/download"
    )
    assert auditor.events[0]["entity_type"] == "expense_records"
    assert auditor.events[0]["metadata"]["action"] == "finance.expense.created"


def test_expense_rejects_nonexistent_document() -> None:
    document_id = uuid4()
    service = FinanceService(FakeFinanceRepository())
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    response = client.post(
        "/api/v1/finances/expenses",
        headers=auth_header(token),
        json=expense_payload(document_id),
    )

    assert response.status_code == 422
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["errors"][0]["field"] == "receipt_document_id"


def test_expense_rejects_nonexistent_budget_and_category() -> None:
    document_id = uuid4()
    repository = FakeFinanceRepository(
        receipt_document_ids={document_id},
        category_exists=False,
    )
    service = FinanceService(repository)
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    budget_response = client.post(
        "/api/v1/finances/expenses",
        headers=auth_header(token),
        json={**expense_payload(document_id), "budget_id": str(uuid4())},
    )
    category_response = client.post(
        "/api/v1/finances/expenses",
        headers=auth_header(token),
        json=expense_payload(document_id, category_id=uuid4()),
    )

    assert budget_response.status_code == 422
    assert budget_response.json()["errors"][0]["field"] == "budget_id"
    assert category_response.status_code == 422
    assert category_response.json()["errors"][0]["field"] == "category_id"


def test_finance_manager_can_approve_expense_and_audit() -> None:
    expense = build_expense(uuid4(), status=FinancialRecordStatus.PENDING)
    repository = FakeFinanceRepository(expenses=[expense])
    auditor = RecordingAuditor()
    service = FinanceService(repository, auditor)
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    response = client.post(
        f"/api/v1/finances/expenses/{expense.id}/approve",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "APPROVED"
    assert auditor.events[0]["metadata"] == {
        "action": "finance.expense.approved",
        "old_status": "PENDING",
        "new_status": "APPROVED",
    }


def test_expense_cannot_be_approved_twice_or_edited_after_approval() -> None:
    expense = build_expense(uuid4(), status=FinancialRecordStatus.APPROVED)
    service = FinanceService(FakeFinanceRepository(expenses=[expense]))
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    approve_response = client.post(
        f"/api/v1/finances/expenses/{expense.id}/approve",
        headers=auth_header(token),
    )
    patch_response = client.patch(
        f"/api/v1/finances/expenses/{expense.id}",
        headers=auth_header(token),
        json={"description": "Cambio no permitido"},
    )

    assert approve_response.status_code == 409
    assert patch_response.status_code == 409
    assert_standard_response_shape(approve_response.json())
    assert_standard_response_shape(patch_response.json())


def test_budget_and_pending_expense_updates_generate_audit() -> None:
    budget = build_budget(uuid4(), status=BudgetStatus.DRAFT)
    expense = build_expense(uuid4(), status=FinancialRecordStatus.PENDING)
    repository = FakeFinanceRepository(
        budgets=[budget],
        expenses=[expense],
    )
    auditor = RecordingAuditor()
    service = FinanceService(repository, auditor)
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    budget_response = client.patch(
        f"/api/v1/finances/budgets/{budget.id}",
        headers=auth_header(token),
        json={"name": "Presupuesto actualizado"},
    )
    expense_response = client.patch(
        f"/api/v1/finances/expenses/{expense.id}",
        headers=auth_header(token),
        json={"description": "Gasto actualizado"},
    )

    assert budget_response.status_code == 200
    assert expense_response.status_code == 200
    assert [event["metadata"]["action"] for event in auditor.events] == [
        "finance.budget.updated",
        "finance.expense.updated",
    ]


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (f"/api/v1/finances/budgets/{uuid4()}", {"name": None}),
        (f"/api/v1/finances/expenses/{uuid4()}", {"receipt_document_id": None}),
    ],
)
def test_patch_rejects_null_for_required_financial_fields(
    path: str,
    payload: dict[str, object],
) -> None:
    service = FinanceService(FakeFinanceRepository())
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    response = client.patch(
        path,
        headers=auth_header(token),
        json=payload,
    )

    assert response.status_code == 422
    assert_standard_response_shape(response.json())


def test_financial_summary_calculates_income_expenses_balance_and_categories() -> None:
    category_id = uuid4()
    income = [
        build_income(uuid4(), amount=Decimal("1500.00")),
        build_income(uuid4(), amount=Decimal("500.00")),
    ]
    expenses = [
        build_expense(
            uuid4(),
            amount=Decimal("300.00"),
            status=FinancialRecordStatus.APPROVED,
            category_id=category_id,
        ),
        build_expense(
            uuid4(),
            amount=Decimal("200.00"),
            status=FinancialRecordStatus.APPROVED,
            category_id=category_id,
        ),
    ]
    service = FinanceService(
        FakeFinanceRepository(income=income, expenses=expenses)
    )
    client, _, _ = build_client(service)

    response = client.get("/api/v1/finances/summary")

    assert response.status_code == 200
    payload = response.json()
    assert_standard_response_shape(payload)
    assert Decimal(payload["data"]["total_income"]) == Decimal("2000.00")
    assert Decimal(payload["data"]["total_expenses"]) == Decimal("500.00")
    assert Decimal(payload["data"]["balance"]) == Decimal("1500.00")
    assert Decimal(payload["data"]["expenses_by_category"][0]["total"]) == Decimal(
        "500.00"
    )


def test_admin_summary_includes_pending_records_but_public_summary_does_not() -> None:
    pending_expense = build_expense(
        uuid4(),
        amount=Decimal("400.00"),
        status=FinancialRecordStatus.PENDING,
    )
    service = FinanceService(
        FakeFinanceRepository(expenses=[pending_expense])
    )
    public_client, _, _ = build_client(service)
    admin_client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    public_response = public_client.get("/api/v1/finances/summary")
    admin_response = admin_client.get(
        "/api/v1/finances/summary",
        headers=auth_header(token),
    )

    assert Decimal(public_response.json()["data"]["total_expenses"]) == Decimal("0")
    assert Decimal(admin_response.json()["data"]["total_expenses"]) == Decimal(
        "400.00"
    )


def test_service_create_income_and_expense_commit_with_audit() -> None:
    asyncio.run(_run_service_create_checks())


async def _run_service_create_checks() -> None:
    actor = build_actor()
    document_id = uuid4()
    repository = FakeFinanceRepository(receipt_document_ids={document_id})
    auditor = RecordingAuditor()
    service = FinanceService(repository, auditor)

    income = await service.create_income(
        actor=actor,
        payload=IncomeCreateRequest(
            amount=Decimal("100.00"),
            source="Donacion",
            received_on=date.today(),
        ),
    )
    expense = await service.create_expense(
        actor=actor,
        payload=ExpenseCreateRequest(
            amount=Decimal("40.00"),
            description="Material",
            spent_on=date.today(),
            receipt_document_id=document_id,
        ),
    )

    assert repository.committed is True
    assert income.status == FinancialRecordStatus.APPROVED
    assert expense.status == FinancialRecordStatus.PENDING
    assert [event["metadata"]["action"] for event in auditor.events] == [
        "finance.income.created",
        "finance.expense.created",
    ]


def test_approve_missing_expense_returns_404() -> None:
    service = FinanceService(FakeFinanceRepository())
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    response = client.post(
        f"/api/v1/finances/expenses/{uuid4()}/approve",
        headers=auth_header(token),
    )

    assert response.status_code == 404
    assert_standard_response_shape(response.json())


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/api/v1/finances/budgets", budget_payload()),
        ("post", "/api/v1/finances/income", income_payload()),
        ("post", "/api/v1/finances/expenses", expense_payload(uuid4())),
        ("patch", f"/api/v1/finances/budgets/{uuid4()}", {"name": "Cambio"}),
        (
            "patch",
            f"/api/v1/finances/expenses/{uuid4()}",
            {"description": "Cambio"},
        ),
        ("post", f"/api/v1/finances/expenses/{uuid4()}/approve", None),
    ],
)
def test_all_administrative_finance_routes_require_finances_manage(
    method: str,
    path: str,
    payload: dict[str, object] | None,
) -> None:
    service = FinanceService(FakeFinanceRepository())
    client, token, _ = build_client(service)

    response = getattr(client, method)(
        path,
        headers=auth_header(token),
        json=payload,
    )

    assert response.status_code == 403
    assert_standard_response_shape(response.json())
    assert response.json()["message"] == "Permisos insuficientes"


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/finances/budgets?status=DRAFT",
        "/api/v1/finances/income?status=PENDING",
        "/api/v1/finances/expenses?status=PENDING",
    ],
)
def test_authenticated_user_without_permission_cannot_use_admin_filters(
    path: str,
) -> None:
    service = FinanceService(FakeFinanceRepository())
    client, token, _ = build_client(service)

    response = client.get(path, headers=auth_header(token))

    assert response.status_code == 403
    assert_standard_response_shape(response.json())


def test_authenticated_user_without_permission_cannot_view_draft_budget() -> None:
    draft = build_budget(uuid4(), status=BudgetStatus.DRAFT)
    service = FinanceService(FakeFinanceRepository(budgets=[draft]))
    client, token, _ = build_client(service)

    response = client.get(
        f"/api/v1/finances/budgets/{draft.id}",
        headers=auth_header(token),
    )

    assert response.status_code == 403
    assert_standard_response_shape(response.json())


@pytest.mark.parametrize(
    ("record_type", "date_value"),
    [
        ("income", None),
        ("income", "fecha-invalida"),
        ("expense", None),
        ("expense", "fecha-invalida"),
    ],
)
def test_income_and_expense_reject_missing_or_invalid_dates(
    record_type: str,
    date_value: str | None,
) -> None:
    document_id = uuid4()
    service = FinanceService(
        FakeFinanceRepository(receipt_document_ids={document_id})
    )
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )
    if record_type == "income":
        payload = income_payload()
        date_field = "received_on"
    else:
        payload = expense_payload(document_id)
        date_field = "spent_on"
    if date_value is None:
        payload.pop(date_field)
    else:
        payload[date_field] = date_value

    response = client.post(
        f"/api/v1/finances/{record_type}",
        headers=auth_header(token),
        json=payload,
    )

    assert response.status_code == 422
    assert_standard_response_shape(response.json())


def test_budget_rejects_negative_total_amount() -> None:
    service = FinanceService(FakeFinanceRepository())
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )
    payload = budget_payload()
    payload["total_amount"] = "-0.01"

    response = client.post(
        "/api/v1/finances/budgets",
        headers=auth_header(token),
        json=payload,
    )

    assert response.status_code == 422
    assert_standard_response_shape(response.json())


@pytest.mark.parametrize(
    ("current_status", "requested_status"),
    [
        (BudgetStatus.DRAFT, BudgetStatus.ACTIVE),
        (BudgetStatus.ACTIVE, BudgetStatus.CLOSED),
        (BudgetStatus.CLOSED, BudgetStatus.ARCHIVED),
    ],
)
def test_budget_allows_defined_status_transitions_and_audits(
    current_status: BudgetStatus,
    requested_status: BudgetStatus,
) -> None:
    budget = build_budget(uuid4(), status=current_status)
    repository = FakeFinanceRepository(budgets=[budget])
    auditor = RecordingAuditor()
    service = FinanceService(repository, auditor)
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    response = client.patch(
        f"/api/v1/finances/budgets/{budget.id}",
        headers=auth_header(token),
        json={"status": requested_status.value},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == requested_status.value
    assert auditor.events[0]["metadata"]["old_status"] == current_status.value
    assert auditor.events[0]["metadata"]["new_status"] == requested_status.value


@pytest.mark.parametrize(
    ("current_status", "requested_status"),
    [
        (BudgetStatus.DRAFT, BudgetStatus.CLOSED),
        (BudgetStatus.ACTIVE, BudgetStatus.DRAFT),
        (BudgetStatus.CLOSED, BudgetStatus.ACTIVE),
    ],
)
def test_budget_rejects_invalid_status_transitions(
    current_status: BudgetStatus,
    requested_status: BudgetStatus,
) -> None:
    budget = build_budget(uuid4(), status=current_status)
    service = FinanceService(FakeFinanceRepository(budgets=[budget]))
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    response = client.patch(
        f"/api/v1/finances/budgets/{budget.id}",
        headers=auth_header(token),
        json={"status": requested_status.value},
    )

    assert response.status_code == 409
    assert_standard_response_shape(response.json())


def test_archived_budget_cannot_be_edited() -> None:
    budget = build_budget(uuid4(), status=BudgetStatus.ARCHIVED)
    service = FinanceService(FakeFinanceRepository(budgets=[budget]))
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    response = client.patch(
        f"/api/v1/finances/budgets/{budget.id}",
        headers=auth_header(token),
        json={"name": "No permitido"},
    )

    assert response.status_code == 409
    assert_standard_response_shape(response.json())


def test_budget_partial_update_revalidates_complete_period() -> None:
    budget = build_budget(
        uuid4(),
        status=BudgetStatus.DRAFT,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
    )
    service = FinanceService(FakeFinanceRepository(budgets=[budget]))
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    response = client.patch(
        f"/api/v1/finances/budgets/{budget.id}",
        headers=auth_header(token),
        json={"period_start": "2027-01-01"},
    )

    assert response.status_code == 422
    assert_standard_response_shape(response.json())


def test_invalid_student_center_and_income_budget_are_rejected() -> None:
    repository = FakeFinanceRepository(student_center_exists=False)
    service = FinanceService(repository)
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    budget_response = client.post(
        "/api/v1/finances/budgets",
        headers=auth_header(token),
        json={**budget_payload(), "student_center_id": str(uuid4())},
    )
    income_response = client.post(
        "/api/v1/finances/income",
        headers=auth_header(token),
        json={**income_payload(), "budget_id": str(uuid4())},
    )

    assert budget_response.status_code == 422
    assert budget_response.json()["errors"][0]["field"] == "student_center_id"
    assert income_response.status_code == 422
    assert income_response.json()["errors"][0]["field"] == "budget_id"


def test_pending_expense_can_replace_receipt_document_and_audits() -> None:
    old_document_id = uuid4()
    new_document_id = uuid4()
    expense = build_expense(
        uuid4(),
        status=FinancialRecordStatus.PENDING,
        receipt_document_id=old_document_id,
    )
    repository = FakeFinanceRepository(
        expenses=[expense],
        receipt_document_ids={old_document_id, new_document_id},
    )
    auditor = RecordingAuditor()
    service = FinanceService(repository, auditor)
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    response = client.patch(
        f"/api/v1/finances/expenses/{expense.id}",
        headers=auth_header(token),
        json={"receipt_document_id": str(new_document_id)},
    )

    assert response.status_code == 200
    assert response.json()["data"]["receipt_document_id"] == str(new_document_id)
    assert response.json()["data"]["receipt_download_url"] == (
        f"/api/v1/documents/{new_document_id}/download"
    )
    assert auditor.events[0]["metadata"]["action"] == "finance.expense.updated"


def test_pending_expense_rejects_nonexistent_replacement_receipt() -> None:
    expense = build_expense(uuid4(), status=FinancialRecordStatus.PENDING)
    service = FinanceService(FakeFinanceRepository(expenses=[expense]))
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    response = client.patch(
        f"/api/v1/finances/expenses/{expense.id}",
        headers=auth_header(token),
        json={"receipt_document_id": str(uuid4())},
    )

    assert response.status_code == 422
    assert_standard_response_shape(response.json())
    assert response.json()["errors"][0]["field"] == "receipt_document_id"


@pytest.mark.parametrize(
    "status",
    [
        FinancialRecordStatus.APPROVED,
        FinancialRecordStatus.REJECTED,
        FinancialRecordStatus.VOID,
    ],
)
def test_terminal_expenses_cannot_be_edited_or_approved(
    status: FinancialRecordStatus,
) -> None:
    expense = build_expense(uuid4(), status=status)
    service = FinanceService(FakeFinanceRepository(expenses=[expense]))
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    patch_response = client.patch(
        f"/api/v1/finances/expenses/{expense.id}",
        headers=auth_header(token),
        json={"description": "No permitido"},
    )
    approve_response = client.post(
        f"/api/v1/finances/expenses/{expense.id}/approve",
        headers=auth_header(token),
    )

    assert patch_response.status_code == 409
    assert approve_response.status_code == 409
    assert_standard_response_shape(patch_response.json())
    assert_standard_response_shape(approve_response.json())


def test_financial_summary_preserves_decimal_cent_precision() -> None:
    category_id = uuid4()
    income = [
        build_income(uuid4(), amount=Decimal("0.10")),
        build_income(uuid4(), amount=Decimal("0.20")),
    ]
    expenses = [
        build_expense(
            uuid4(),
            amount=Decimal("0.03"),
            status=FinancialRecordStatus.APPROVED,
            category_id=category_id,
        ),
    ]
    service = FinanceService(
        FakeFinanceRepository(income=income, expenses=expenses)
    )
    client, _, _ = build_client(service)

    response = client.get("/api/v1/finances/summary")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_income"] == "0.30"
    assert data["total_expenses"] == "0.03"
    assert data["balance"] == "0.27"
    assert data["expenses_by_category"][0]["total"] == "0.03"


def test_public_and_admin_summary_apply_all_status_rules() -> None:
    income = [
        build_income(
            uuid4(),
            amount=Decimal("10.00"),
            status=FinancialRecordStatus.APPROVED,
        ),
        build_income(
            uuid4(),
            amount=Decimal("20.00"),
            status=FinancialRecordStatus.PENDING,
        ),
        build_income(
            uuid4(),
            amount=Decimal("40.00"),
            status=FinancialRecordStatus.REJECTED,
        ),
    ]
    expenses = [
        build_expense(
            uuid4(),
            amount=Decimal("3.00"),
            status=FinancialRecordStatus.APPROVED,
        ),
        build_expense(
            uuid4(),
            amount=Decimal("4.00"),
            status=FinancialRecordStatus.PENDING,
        ),
        build_expense(
            uuid4(),
            amount=Decimal("8.00"),
            status=FinancialRecordStatus.VOID,
        ),
    ]
    service = FinanceService(
        FakeFinanceRepository(income=income, expenses=expenses)
    )
    public_client, _, _ = build_client(service)
    admin_client, admin_token, _ = build_client(
        service,
        permissions=[PermissionCode.FINANCES_MANAGE.value],
    )

    public_data = public_client.get("/api/v1/finances/summary").json()["data"]
    admin_data = admin_client.get(
        "/api/v1/finances/summary",
        headers=auth_header(admin_token),
    ).json()["data"]

    assert public_data["total_income"] == "10.00"
    assert public_data["total_expenses"] == "3.00"
    assert public_data["balance"] == "7.00"
    assert admin_data["total_income"] == "30.00"
    assert admin_data["total_expenses"] == "7.00"
    assert admin_data["balance"] == "23.00"


def test_financial_list_pagination_preserves_total() -> None:
    budgets = [
        build_budget(uuid4(), name=f"Presupuesto {index}")
        for index in range(3)
    ]
    service = FinanceService(FakeFinanceRepository(budgets=budgets))
    client, _, _ = build_client(service)

    response = client.get("/api/v1/finances/budgets?limit=1&offset=1")

    assert response.status_code == 200
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["data"]["total"] == 3
    assert payload["data"]["limit"] == 1
    assert payload["data"]["offset"] == 1
    assert len(payload["data"]["items"]) == 1
