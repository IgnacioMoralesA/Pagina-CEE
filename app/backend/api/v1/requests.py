from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse

from app.backend.auth.dependencies import require_auth, require_permissions
from app.backend.auth.permissions import PermissionCode
from app.backend.auth.schemas import UserPrincipal
from app.backend.core.config import Settings, get_settings
from app.backend.core.responses import ApiResponse, success_response
from app.backend.documents.dependencies import get_document_service
from app.backend.documents.schemas import RequestAttachmentResponse
from app.backend.documents.service import DocumentService
from app.backend.files.multipart import parse_multipart_upload
from app.backend.student_requests.dependencies import get_student_request_service
from app.backend.student_requests.schemas import (
    PaginatedResponse,
    RequestApproveRequest,
    RequestAssignRequest,
    RequestCloseRequest,
    RequestCommentCreateRequest,
    RequestCommentResponse,
    RequestCreateRequest,
    RequestObserveRequest,
    RequestRejectRequest,
    RequestStatus,
    RequestUpdateRequest,
    StudentRequestResponse,
)
from app.backend.student_requests.service import StudentRequestService


router = APIRouter()


@router.get(
    "/requests",
    response_model=ApiResponse[PaginatedResponse[StudentRequestResponse]],
)
async def list_requests(
    scope: Literal["mine", "all"] | None = Query(default=None),
    status: RequestStatus | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: UserPrincipal = Depends(require_auth),
    request_service: StudentRequestService = Depends(get_student_request_service),
) -> ApiResponse[PaginatedResponse[StudentRequestResponse]]:
    requests = await request_service.list_requests(
        actor=current_user,
        scope=scope,
        status=status,
        category_id=category_id,
        limit=limit,
        offset=offset,
    )
    return success_response(requests, "Solicitudes obtenidas")


@router.post(
    "/requests",
    response_model=ApiResponse[StudentRequestResponse],
    status_code=201,
)
async def create_request(
    payload: RequestCreateRequest,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.REQUESTS_CREATE.value)
    ),
    request_service: StudentRequestService = Depends(get_student_request_service),
) -> ApiResponse[StudentRequestResponse]:
    student_request = await request_service.create_request(
        actor=current_user,
        payload=payload,
    )
    return success_response(student_request, "Solicitud creada")


@router.get("/requests/{request_id}", response_model=ApiResponse[StudentRequestResponse])
async def get_request(
    request_id: UUID,
    current_user: UserPrincipal = Depends(require_auth),
    request_service: StudentRequestService = Depends(get_student_request_service),
) -> ApiResponse[StudentRequestResponse]:
    student_request = await request_service.get_request(
        actor=current_user,
        request_id=request_id,
    )
    return success_response(student_request, "Solicitud obtenida")


@router.patch(
    "/requests/{request_id}",
    response_model=ApiResponse[StudentRequestResponse],
)
async def update_request(
    request_id: UUID,
    payload: RequestUpdateRequest,
    current_user: UserPrincipal = Depends(require_auth),
    request_service: StudentRequestService = Depends(get_student_request_service),
) -> ApiResponse[StudentRequestResponse]:
    student_request = await request_service.update_request(
        actor=current_user,
        request_id=request_id,
        payload=payload,
    )
    return success_response(student_request, "Solicitud actualizada")


@router.post(
    "/requests/{request_id}/assign",
    response_model=ApiResponse[StudentRequestResponse],
)
async def assign_request(
    request_id: UUID,
    payload: RequestAssignRequest,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.REQUESTS_MANAGE.value)
    ),
    request_service: StudentRequestService = Depends(get_student_request_service),
) -> ApiResponse[StudentRequestResponse]:
    student_request = await request_service.assign_request(
        actor=current_user,
        request_id=request_id,
        payload=payload,
    )
    return success_response(student_request, "Solicitud asignada")


@router.post(
    "/requests/{request_id}/observe",
    response_model=ApiResponse[StudentRequestResponse],
)
async def observe_request(
    request_id: UUID,
    payload: RequestObserveRequest,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.REQUESTS_MANAGE.value)
    ),
    request_service: StudentRequestService = Depends(get_student_request_service),
) -> ApiResponse[StudentRequestResponse]:
    student_request = await request_service.observe_request(
        actor=current_user,
        request_id=request_id,
        payload=payload,
    )
    return success_response(student_request, "Solicitud observada")


@router.post(
    "/requests/{request_id}/approve",
    response_model=ApiResponse[StudentRequestResponse],
)
async def approve_request(
    request_id: UUID,
    payload: RequestApproveRequest | None = None,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.REQUESTS_MANAGE.value)
    ),
    request_service: StudentRequestService = Depends(get_student_request_service),
) -> ApiResponse[StudentRequestResponse]:
    student_request = await request_service.approve_request(
        actor=current_user,
        request_id=request_id,
        payload=payload or RequestApproveRequest(),
    )
    return success_response(student_request, "Solicitud aprobada")


@router.post(
    "/requests/{request_id}/reject",
    response_model=ApiResponse[StudentRequestResponse],
)
async def reject_request(
    request_id: UUID,
    payload: RequestRejectRequest,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.REQUESTS_MANAGE.value)
    ),
    request_service: StudentRequestService = Depends(get_student_request_service),
) -> ApiResponse[StudentRequestResponse]:
    student_request = await request_service.reject_request(
        actor=current_user,
        request_id=request_id,
        payload=payload,
    )
    return success_response(student_request, "Solicitud rechazada")


@router.post(
    "/requests/{request_id}/close",
    response_model=ApiResponse[StudentRequestResponse],
)
async def close_request(
    request_id: UUID,
    payload: RequestCloseRequest | None = None,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.REQUESTS_MANAGE.value)
    ),
    request_service: StudentRequestService = Depends(get_student_request_service),
) -> ApiResponse[StudentRequestResponse]:
    student_request = await request_service.close_request(
        actor=current_user,
        request_id=request_id,
        payload=payload or RequestCloseRequest(),
    )
    return success_response(student_request, "Solicitud cerrada")


@router.post(
    "/requests/{request_id}/comments",
    response_model=ApiResponse[RequestCommentResponse],
    status_code=201,
)
async def create_request_comment(
    request_id: UUID,
    payload: RequestCommentCreateRequest,
    current_user: UserPrincipal = Depends(require_auth),
    request_service: StudentRequestService = Depends(get_student_request_service),
) -> ApiResponse[RequestCommentResponse]:
    comment = await request_service.create_comment(
        actor=current_user,
        request_id=request_id,
        payload=payload,
    )
    return success_response(comment, "Comentario registrado")


@router.post(
    "/requests/{request_id}/attachments",
    response_model=ApiResponse[RequestAttachmentResponse],
    status_code=201,
)
async def create_request_attachment(
    request_id: UUID,
    request: Request,
    current_user: UserPrincipal = Depends(require_auth),
    settings: Settings = Depends(get_settings),
    document_service: DocumentService = Depends(get_document_service),
) -> ApiResponse[RequestAttachmentResponse]:
    parsed = await parse_multipart_upload(
        request,
        max_file_size_bytes=settings.max_upload_size_bytes,
    )
    attachment = await document_service.upload_request_attachment(
        actor=current_user,
        request_id=request_id,
        file=parsed.file,
    )
    return success_response(attachment, "Adjunto registrado")


@router.get(
    "/requests/{request_id}/attachments",
    response_model=ApiResponse[list[RequestAttachmentResponse]],
)
async def list_request_attachments(
    request_id: UUID,
    current_user: UserPrincipal = Depends(require_auth),
    document_service: DocumentService = Depends(get_document_service),
) -> ApiResponse[list[RequestAttachmentResponse]]:
    attachments = await document_service.list_request_attachments(
        actor=current_user,
        request_id=request_id,
    )
    return success_response(attachments, "Adjuntos obtenidos")


@router.get("/requests/{request_id}/attachments/{attachment_id}/download")
async def download_request_attachment(
    request_id: UUID,
    attachment_id: UUID,
    current_user: UserPrincipal = Depends(require_auth),
    document_service: DocumentService = Depends(get_document_service),
) -> FileResponse:
    descriptor = await document_service.download_request_attachment(
        actor=current_user,
        request_id=request_id,
        attachment_id=attachment_id,
    )
    return FileResponse(
        path=descriptor.path,
        media_type=descriptor.mime_type,
        filename=descriptor.file_name,
    )
