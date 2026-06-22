from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.db.session import get_session
from app.backend.users.service import UserService, create_user_service


async def get_user_service(
    db: AsyncSession = Depends(get_session),
) -> UserService:
    return create_user_service(db)
