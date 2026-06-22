from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.content.service import ContentService, create_content_service
from app.backend.db.session import get_session


def get_content_service(
    db: AsyncSession = Depends(get_session),
) -> ContentService:
    return create_content_service(db)
