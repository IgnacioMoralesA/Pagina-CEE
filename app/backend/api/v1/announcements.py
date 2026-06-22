from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.backend.auth.dependencies import require_permissions
from app.backend.auth.permissions import PermissionCode
from app.backend.auth.schemas import UserPrincipal
from app.backend.content.dependencies import get_content_service
from app.backend.content.schemas import (
    AnnouncementCreateRequest,
    AnnouncementResponse,
    AnnouncementUpdateRequest,
    PaginatedResponse,
)
from app.backend.content.service import ContentService
from app.backend.core.responses import ApiResponse, success_response


router = APIRouter()


@router.get(
    "/announcements",
    response_model=ApiResponse[PaginatedResponse[AnnouncementResponse]],
)
async def list_announcements(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    content_service: ContentService = Depends(get_content_service),
) -> ApiResponse[PaginatedResponse[AnnouncementResponse]]:
    announcements = await content_service.list_announcements(
        limit=limit,
        offset=offset,
    )
    return success_response(announcements, "Comunicados obtenidos")


@router.post(
    "/announcements",
    response_model=ApiResponse[AnnouncementResponse],
    status_code=201,
)
async def create_announcement(
    payload: AnnouncementCreateRequest,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.CONTENT_PUBLISH.value)
    ),
    content_service: ContentService = Depends(get_content_service),
) -> ApiResponse[AnnouncementResponse]:
    announcement = await content_service.create_announcement(
        actor=current_user,
        payload=payload,
    )
    return success_response(announcement, "Comunicado creado")


@router.patch(
    "/announcements/{announcement_id}",
    response_model=ApiResponse[AnnouncementResponse],
)
async def update_announcement(
    announcement_id: UUID,
    payload: AnnouncementUpdateRequest,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.CONTENT_PUBLISH.value)
    ),
    content_service: ContentService = Depends(get_content_service),
) -> ApiResponse[AnnouncementResponse]:
    announcement = await content_service.update_announcement(
        actor=current_user,
        announcement_id=announcement_id,
        payload=payload,
    )
    return success_response(announcement, "Comunicado actualizado")


@router.post(
    "/announcements/{announcement_id}/publish",
    response_model=ApiResponse[AnnouncementResponse],
)
async def publish_announcement(
    announcement_id: UUID,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.CONTENT_PUBLISH.value)
    ),
    content_service: ContentService = Depends(get_content_service),
) -> ApiResponse[AnnouncementResponse]:
    announcement = await content_service.publish_announcement(
        actor=current_user,
        announcement_id=announcement_id,
    )
    return success_response(announcement, "Comunicado publicado")
