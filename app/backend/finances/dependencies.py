from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.db.session import get_session
from app.backend.finances.service import FinanceService, create_finance_service


def get_finance_service(
    db: AsyncSession = Depends(get_session),
) -> FinanceService:
    return create_finance_service(db)
