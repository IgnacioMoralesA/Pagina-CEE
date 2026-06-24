from __future__ import annotations

from fastapi import APIRouter

from app.backend.api.v1.access_control import router as access_control_router
from app.backend.api.v1.announcements import router as announcements_router
from app.backend.api.v1.auth import router as auth_router
from app.backend.api.v1.documents import router as documents_router
from app.backend.api.v1.events import router as events_router
from app.backend.api.v1.finances import router as finances_router
from app.backend.api.v1.health import router as health_router
from app.backend.api.v1.news import router as news_router
from app.backend.api.v1.requests import router as requests_router
from app.backend.api.v1.users import router as users_router


api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(access_control_router, tags=["access-control"])
api_router.include_router(news_router, tags=["news"])
api_router.include_router(announcements_router, tags=["announcements"])
api_router.include_router(events_router, tags=["events"])
api_router.include_router(requests_router, tags=["requests"])
api_router.include_router(documents_router, tags=["documents"])
api_router.include_router(finances_router, tags=["finances"])
