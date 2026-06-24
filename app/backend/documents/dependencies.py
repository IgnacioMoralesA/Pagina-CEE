from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.core.config import Settings, get_settings
from app.backend.db.session import get_session
from app.backend.documents.service import DocumentService, create_document_service


def get_document_service(
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> DocumentService:
    return create_document_service(db, settings)
