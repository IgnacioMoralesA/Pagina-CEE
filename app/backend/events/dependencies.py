from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.db.session import get_session
from app.backend.events.service import EventService, create_event_service


def get_event_service(
    db: AsyncSession = Depends(get_session),
) -> EventService:
    return create_event_service(db)
