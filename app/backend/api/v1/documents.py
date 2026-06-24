from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.backend.auth.dependencies import optional_auth, require_permissions
from app.backend.auth.permissions import PermissionCode
from app.backend.auth.schemas import UserPrincipal
from app.backend.core.config import Settings, get_settings
from app.backend.core.errors import AppError
from app.backend.core.responses import ApiResponse, ErrorDetail, success_response
from app.backend.documents.dependencies import get_document_service
from app.backend.documents.schemas import (
    DocumentCreateRequest,
    DocumentResponse,
    DocumentStatus,
    DocumentUpdateRequest,
    DocumentVisibility,
    PaginatedResponse,
)
from app.backend.documents.service import DocumentService
from app.backend.files.multipart import parse_multipart_upload


router = APIRouter()


@router.get("/documents", response_model=ApiResponse[PaginatedResponse[DocumentResponse]])
async def list_documents(
    status: DocumentStatus | None = Query(default=None),
    visibility: DocumentVisibility | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: UserPrincipal | None = Depends(optional_auth),
    document_service: DocumentService = Depends(get_document_service),
) -> ApiResponse[PaginatedResponse[DocumentResponse]]:
    documents = await document_service.list_documents(
        current_user=current_user,
        status=status,
        visibility=visibility,
        category_id=category_id,
        limit=limit,
        offset=offset,
    )
    return success_response(documents, "Documentos obtenidos")


@router.post("/documents", response_model=ApiResponse[DocumentResponse], status_code=201)
async def create_document(
    request: Request,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.DOCUMENTS_MANAGE.value)
    ),
    settings: Settings = Depends(get_settings),
    document_service: DocumentService = Depends(get_document_service),
) -> ApiResponse[DocumentResponse]:
    parsed = await parse_multipart_upload(
        request,
        max_file_size_bytes=settings.max_upload_size_bytes,
    )
    document = await document_service.create_document(
        actor=current_user,
        payload=_document_create_payload(parsed.fields),
        file=parsed.file,
    )
    return success_response(document, "Documento creado")


@router.get("/documents/{document_id}", response_model=ApiResponse[DocumentResponse])
async def get_document(
    document_id: UUID,
    current_user: UserPrincipal | None = Depends(optional_auth),
    document_service: DocumentService = Depends(get_document_service),
) -> ApiResponse[DocumentResponse]:
    document = await document_service.get_document(
        current_user=current_user,
        document_id=document_id,
    )
    return success_response(document, "Documento obtenido")


@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: UUID,
    current_user: UserPrincipal | None = Depends(optional_auth),
    document_service: DocumentService = Depends(get_document_service),
) -> FileResponse:
    descriptor = await document_service.download_document(
        current_user=current_user,
        document_id=document_id,
    )
    return FileResponse(
        path=descriptor.path,
        media_type=descriptor.mime_type,
        filename=descriptor.file_name,
    )


@router.patch("/documents/{document_id}", response_model=ApiResponse[DocumentResponse])
async def update_document(
    document_id: UUID,
    payload: DocumentUpdateRequest,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.DOCUMENTS_MANAGE.value)
    ),
    document_service: DocumentService = Depends(get_document_service),
) -> ApiResponse[DocumentResponse]:
    document = await document_service.update_document(
        actor=current_user,
        document_id=document_id,
        payload=payload,
    )
    return success_response(document, "Documento actualizado")


@router.delete("/documents/{document_id}", response_model=ApiResponse[DocumentResponse])
async def delete_document(
    document_id: UUID,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.DOCUMENTS_MANAGE.value)
    ),
    document_service: DocumentService = Depends(get_document_service),
) -> ApiResponse[DocumentResponse]:
    document = await document_service.delete_document(
        actor=current_user,
        document_id=document_id,
    )
    return success_response(document, "Documento eliminado")


def _document_form_fields(fields: dict[str, str]) -> dict[str, str]:
    allowed = {"title", "description", "category_id", "visibility", "status"}
    return {
        key: value
        for key, value in fields.items()
        if key in allowed and value.strip() != ""
    }


def _document_create_payload(fields: dict[str, str]) -> DocumentCreateRequest:
    try:
        return DocumentCreateRequest(**_document_form_fields(fields))
    except ValidationError as exc:
        errors = [
            ErrorDetail(
                field=".".join(str(part) for part in error["loc"]),
                detail=error["msg"],
            )
            for error in exc.errors()
        ]
        raise AppError(status_code=422, message="Solicitud invalida", errors=errors) from exc
