from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.backend.core.config import Settings, get_settings
from app.backend.core.errors import AppError


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    global _engine
    if _engine is None:
        resolved_settings = settings or get_settings()
        _engine = create_async_engine(
            resolved_settings.database_url,
            pool_pre_ping=True,
            future=True,
        )
    return _engine


def get_session_factory(
    settings: Settings | None = None,
) -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(settings),
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    try:
        session_factory = get_session_factory()
    except Exception as exc:  # pragma: no cover - depends on local drivers.
        raise AppError(
            status_code=503,
            message="Base de datos no disponible",
        ) from exc

    async with session_factory() as session:
        yield session


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
