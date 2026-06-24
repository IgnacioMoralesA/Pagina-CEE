from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.db.session import get_session
from app.backend.student_requests.service import (
    StudentRequestService,
    create_student_request_service,
)


def get_student_request_service(
    db: AsyncSession = Depends(get_session),
) -> StudentRequestService:
    return create_student_request_service(db)
