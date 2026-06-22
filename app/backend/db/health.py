from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import text

from app.backend.db.session import get_engine


class DatabaseHealth(BaseModel):
    status: str
    detail: str | None = None


async def check_database_connection() -> DatabaseHealth:
    try:
        engine = get_engine()
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return DatabaseHealth(status="ok")
    except Exception:
        return DatabaseHealth(status="unavailable")
