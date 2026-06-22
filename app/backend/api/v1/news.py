from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.backend.auth.dependencies import optional_auth, require_permissions
from app.backend.auth.permissions import PermissionCode
from app.backend.auth.schemas import UserPrincipal
from app.backend.content.dependencies import get_content_service
from app.backend.content.schemas import (
    NewsCreateRequest,
    NewsResponse,
    NewsUpdateRequest,
    PaginatedResponse,
    PublicationStatus,
)
from app.backend.content.service import ContentService
from app.backend.core.responses import ApiResponse, success_response


router = APIRouter()


@router.get("/news", response_model=ApiResponse[PaginatedResponse[NewsResponse]])
async def list_news(
    status: PublicationStatus | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: UserPrincipal | None = Depends(optional_auth),
    content_service: ContentService = Depends(get_content_service),
) -> ApiResponse[PaginatedResponse[NewsResponse]]:
    news = await content_service.list_news(
        current_user=current_user,
        status=status,
        category_id=category_id,
        limit=limit,
        offset=offset,
    )
    return success_response(news, "Noticias obtenidas")


@router.get("/news/{news_id}", response_model=ApiResponse[NewsResponse])
async def get_news(
    news_id: UUID,
    current_user: UserPrincipal | None = Depends(optional_auth),
    content_service: ContentService = Depends(get_content_service),
) -> ApiResponse[NewsResponse]:
    news = await content_service.get_news(
        news_id=news_id,
        current_user=current_user,
    )
    return success_response(news, "Noticia obtenida")


@router.post("/news", response_model=ApiResponse[NewsResponse], status_code=201)
async def create_news(
    payload: NewsCreateRequest,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.CONTENT_PUBLISH.value)
    ),
    content_service: ContentService = Depends(get_content_service),
) -> ApiResponse[NewsResponse]:
    news = await content_service.create_news(actor=current_user, payload=payload)
    return success_response(news, "Noticia creada")


@router.patch("/news/{news_id}", response_model=ApiResponse[NewsResponse])
async def update_news(
    news_id: UUID,
    payload: NewsUpdateRequest,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.CONTENT_PUBLISH.value)
    ),
    content_service: ContentService = Depends(get_content_service),
) -> ApiResponse[NewsResponse]:
    news = await content_service.update_news(
        actor=current_user,
        news_id=news_id,
        payload=payload,
    )
    return success_response(news, "Noticia actualizada")


@router.delete("/news/{news_id}", response_model=ApiResponse[NewsResponse])
async def archive_news(
    news_id: UUID,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.CONTENT_PUBLISH.value)
    ),
    content_service: ContentService = Depends(get_content_service),
) -> ApiResponse[NewsResponse]:
    news = await content_service.archive_news(actor=current_user, news_id=news_id)
    return success_response(news, "Noticia archivada")


@router.post("/news/{news_id}/publish", response_model=ApiResponse[NewsResponse])
async def publish_news(
    news_id: UUID,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.CONTENT_PUBLISH.value)
    ),
    content_service: ContentService = Depends(get_content_service),
) -> ApiResponse[NewsResponse]:
    news = await content_service.publish_news(actor=current_user, news_id=news_id)
    return success_response(news, "Noticia publicada")
