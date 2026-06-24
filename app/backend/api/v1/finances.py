from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.backend.auth.dependencies import optional_auth, require_permissions
from app.backend.auth.permissions import PermissionCode
from app.backend.auth.schemas import UserPrincipal
from app.backend.core.responses import ApiResponse, success_response
from app.backend.finances.dependencies import get_finance_service
from app.backend.finances.schemas import (
    BudgetCreateRequest,
    BudgetResponse,
    BudgetStatus,
    BudgetUpdateRequest,
    ExpenseCreateRequest,
    ExpenseResponse,
    ExpenseUpdateRequest,
    FinancialRecordStatus,
    FinancialSummaryResponse,
    IncomeCreateRequest,
    IncomeResponse,
    PaginatedResponse,
)
from app.backend.finances.service import FinanceService


router = APIRouter(prefix="/finances")


@router.get(
    "/budgets",
    response_model=ApiResponse[PaginatedResponse[BudgetResponse]],
)
async def list_budgets(
    status: BudgetStatus | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: UserPrincipal | None = Depends(optional_auth),
    finance_service: FinanceService = Depends(get_finance_service),
) -> ApiResponse[PaginatedResponse[BudgetResponse]]:
    budgets = await finance_service.list_budgets(
        current_user=current_user,
        status=status,
        limit=limit,
        offset=offset,
    )
    return success_response(budgets, "Presupuestos obtenidos")


@router.post(
    "/budgets",
    response_model=ApiResponse[BudgetResponse],
    status_code=201,
)
async def create_budget(
    payload: BudgetCreateRequest,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.FINANCES_MANAGE.value)
    ),
    finance_service: FinanceService = Depends(get_finance_service),
) -> ApiResponse[BudgetResponse]:
    budget = await finance_service.create_budget(actor=current_user, payload=payload)
    return success_response(budget, "Presupuesto creado")


@router.get(
    "/budgets/{budget_id}",
    response_model=ApiResponse[BudgetResponse],
)
async def get_budget(
    budget_id: UUID,
    current_user: UserPrincipal | None = Depends(optional_auth),
    finance_service: FinanceService = Depends(get_finance_service),
) -> ApiResponse[BudgetResponse]:
    budget = await finance_service.get_budget(
        current_user=current_user,
        budget_id=budget_id,
    )
    return success_response(budget, "Presupuesto obtenido")


@router.patch(
    "/budgets/{budget_id}",
    response_model=ApiResponse[BudgetResponse],
)
async def update_budget(
    budget_id: UUID,
    payload: BudgetUpdateRequest,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.FINANCES_MANAGE.value)
    ),
    finance_service: FinanceService = Depends(get_finance_service),
) -> ApiResponse[BudgetResponse]:
    budget = await finance_service.update_budget(
        actor=current_user,
        budget_id=budget_id,
        payload=payload,
    )
    return success_response(budget, "Presupuesto actualizado")


@router.get(
    "/income",
    response_model=ApiResponse[PaginatedResponse[IncomeResponse]],
)
async def list_income(
    status: FinancialRecordStatus | None = Query(default=None),
    budget_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: UserPrincipal | None = Depends(optional_auth),
    finance_service: FinanceService = Depends(get_finance_service),
) -> ApiResponse[PaginatedResponse[IncomeResponse]]:
    income = await finance_service.list_income(
        current_user=current_user,
        status=status,
        budget_id=budget_id,
        limit=limit,
        offset=offset,
    )
    return success_response(income, "Ingresos obtenidos")


@router.post(
    "/income",
    response_model=ApiResponse[IncomeResponse],
    status_code=201,
)
async def create_income(
    payload: IncomeCreateRequest,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.FINANCES_MANAGE.value)
    ),
    finance_service: FinanceService = Depends(get_finance_service),
) -> ApiResponse[IncomeResponse]:
    income = await finance_service.create_income(actor=current_user, payload=payload)
    return success_response(income, "Ingreso registrado")


@router.get(
    "/expenses",
    response_model=ApiResponse[PaginatedResponse[ExpenseResponse]],
)
async def list_expenses(
    status: FinancialRecordStatus | None = Query(default=None),
    budget_id: UUID | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: UserPrincipal | None = Depends(optional_auth),
    finance_service: FinanceService = Depends(get_finance_service),
) -> ApiResponse[PaginatedResponse[ExpenseResponse]]:
    expenses = await finance_service.list_expenses(
        current_user=current_user,
        status=status,
        budget_id=budget_id,
        category_id=category_id,
        limit=limit,
        offset=offset,
    )
    return success_response(expenses, "Gastos obtenidos")


@router.post(
    "/expenses",
    response_model=ApiResponse[ExpenseResponse],
    status_code=201,
)
async def create_expense(
    payload: ExpenseCreateRequest,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.FINANCES_MANAGE.value)
    ),
    finance_service: FinanceService = Depends(get_finance_service),
) -> ApiResponse[ExpenseResponse]:
    expense = await finance_service.create_expense(actor=current_user, payload=payload)
    return success_response(expense, "Gasto registrado")


@router.patch(
    "/expenses/{expense_id}",
    response_model=ApiResponse[ExpenseResponse],
)
async def update_expense(
    expense_id: UUID,
    payload: ExpenseUpdateRequest,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.FINANCES_MANAGE.value)
    ),
    finance_service: FinanceService = Depends(get_finance_service),
) -> ApiResponse[ExpenseResponse]:
    expense = await finance_service.update_expense(
        actor=current_user,
        expense_id=expense_id,
        payload=payload,
    )
    return success_response(expense, "Gasto actualizado")


@router.post(
    "/expenses/{expense_id}/approve",
    response_model=ApiResponse[ExpenseResponse],
)
async def approve_expense(
    expense_id: UUID,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.FINANCES_MANAGE.value)
    ),
    finance_service: FinanceService = Depends(get_finance_service),
) -> ApiResponse[ExpenseResponse]:
    expense = await finance_service.approve_expense(
        actor=current_user,
        expense_id=expense_id,
    )
    return success_response(expense, "Gasto aprobado")


@router.get(
    "/summary",
    response_model=ApiResponse[FinancialSummaryResponse],
)
async def get_financial_summary(
    current_user: UserPrincipal | None = Depends(optional_auth),
    finance_service: FinanceService = Depends(get_finance_service),
) -> ApiResponse[FinancialSummaryResponse]:
    summary = await finance_service.get_summary(current_user=current_user)
    return success_response(summary, "Resumen financiero obtenido")
