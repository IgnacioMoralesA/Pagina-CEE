from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.audit.service import AuditService
from app.backend.auth.permissions import PermissionCode
from app.backend.auth.schemas import UserPrincipal
from app.backend.core.config import Settings
from app.backend.core.errors import AppError
from app.backend.core.responses import ErrorDetail
from app.backend.documents.schemas import (
    DocumentCreateRequest,
    DocumentResponse,
    DocumentStatus,
    DocumentUpdateRequest,
    DocumentVersionResponse,
    DocumentVisibility,
    PaginatedResponse,
    RequestAttachmentResponse,
)
from app.backend.files.storage import (
    LocalFileStorage,
    StoredFileMetadata,
    UploadedFilePayload,
)
from app.backend.student_requests.schemas import RequestStatus


@dataclass(frozen=True)
class DownloadFileDescriptor:
    path: Path
    file_name: str
    mime_type: str


@dataclass(frozen=True)
class RequestAttachmentContext:
    request_id: UUID
    requester_id: UUID
    status: RequestStatus


class DocumentRepository(Protocol):
    async def category_exists(self, category_id: UUID) -> bool:
        ...

    async def list_documents(
        self,
        *,
        public_only: bool,
        status: DocumentStatus | None,
        visibility: DocumentVisibility | None,
        category_id: UUID | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[DocumentResponse]:
        ...

    async def get_document(self, document_id: UUID) -> DocumentResponse | None:
        ...

    async def create_document_with_version(
        self,
        *,
        owner_id: UUID,
        payload: DocumentCreateRequest,
        stored_file: StoredFileMetadata,
    ) -> DocumentResponse:
        ...

    async def update_document(
        self,
        *,
        document_id: UUID,
        fields: dict[str, Any],
    ) -> DocumentResponse | None:
        ...

    async def archive_document(self, document_id: UUID) -> DocumentResponse | None:
        ...

    async def get_request_context(
        self,
        request_id: UUID,
    ) -> RequestAttachmentContext | None:
        ...

    async def create_request_attachment(
        self,
        *,
        request_id: UUID,
        uploaded_by: UUID,
        stored_file: StoredFileMetadata,
    ) -> RequestAttachmentResponse:
        ...

    async def list_request_attachments(
        self,
        request_id: UUID,
    ) -> list[RequestAttachmentResponse]:
        ...

    async def get_request_attachment(
        self,
        *,
        request_id: UUID,
        attachment_id: UUID,
    ) -> RequestAttachmentResponse | None:
        ...

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...


class AdministrativeAuditor(Protocol):
    async def record_administrative_action(
        self,
        *,
        actor_id: UUID,
        entity_type: str,
        entity_id: UUID | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        ...


class DatabaseDocumentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def category_exists(self, category_id: UUID) -> bool:
        result = await self.db.execute(
            text(
                """
                SELECT 1
                FROM document_categories
                WHERE id = :category_id
                  AND is_active IS TRUE
                  AND deleted_at IS NULL
                """
            ),
            {"category_id": category_id},
        )
        return result.scalar_one_or_none() is not None

    async def list_documents(
        self,
        *,
        public_only: bool,
        status: DocumentStatus | None,
        visibility: DocumentVisibility | None,
        category_id: UUID | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[DocumentResponse]:
        where_sql, params = _document_where(
            public_only=public_only,
            status=status,
            visibility=visibility,
            category_id=category_id,
        )
        count_result = await self.db.execute(
            text(f"SELECT count(*) FROM documents d WHERE {where_sql}"),
            params,
        )
        result = await self.db.execute(
            text(
                f"""
                {_DOCUMENT_SELECT}
                WHERE {where_sql}
                ORDER BY d.published_at DESC NULLS LAST, d.created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {**params, "limit": limit, "offset": offset},
        )
        return PaginatedResponse[DocumentResponse](
            items=[_document_from_row(row) for row in result.mappings()],
            total=int(count_result.scalar_one()),
            limit=limit,
            offset=offset,
        )

    async def get_document(self, document_id: UUID) -> DocumentResponse | None:
        return await self._get_document(document_id, include_deleted=False)

    async def _get_document(
        self,
        document_id: UUID,
        *,
        include_deleted: bool,
    ) -> DocumentResponse | None:
        deleted_filter = "" if include_deleted else "AND d.deleted_at IS NULL"
        result = await self.db.execute(
            text(
                f"""
                {_DOCUMENT_SELECT}
                WHERE d.id = :document_id
                  {deleted_filter}
                """
            ),
            {"document_id": document_id},
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _document_from_row(row)

    async def create_document_with_version(
        self,
        *,
        owner_id: UUID,
        payload: DocumentCreateRequest,
        stored_file: StoredFileMetadata,
    ) -> DocumentResponse:
        result = await self.db.execute(
            text(
                """
                INSERT INTO documents (
                    category_id,
                    title,
                    description,
                    visibility,
                    status,
                    owner_id,
                    published_at
                )
                VALUES (
                    :category_id,
                    :title,
                    :description,
                    :visibility,
                    CAST(:status AS document_status),
                    :owner_id,
                    CASE WHEN :status = 'PUBLISHED' THEN now() ELSE NULL END
                )
                RETURNING id
                """
            ),
            {
                "category_id": payload.category_id,
                "title": payload.title,
                "description": payload.description,
                "visibility": payload.visibility.value,
                "status": payload.status.value,
                "owner_id": owner_id,
            },
        )
        document_id = UUID(str(result.scalar_one()))
        await self.db.execute(
            text(
                """
                INSERT INTO document_versions (
                    document_id,
                    version_number,
                    file_name,
                    file_url,
                    mime_type,
                    file_size_bytes,
                    uploaded_by
                )
                VALUES (
                    :document_id,
                    1,
                    :file_name,
                    :file_url,
                    :mime_type,
                    :file_size_bytes,
                    :uploaded_by
                )
                """
            ),
            {
                "document_id": document_id,
                "file_name": stored_file.file_name,
                "file_url": stored_file.storage_key,
                "mime_type": stored_file.mime_type,
                "file_size_bytes": stored_file.file_size_bytes,
                "uploaded_by": owner_id,
            },
        )
        created = await self.get_document(document_id)
        if created is None:  # pragma: no cover - defensive guard.
            raise AppError(status_code=500, message="Error interno del servidor")
        return created

    async def update_document(
        self,
        *,
        document_id: UUID,
        fields: dict[str, Any],
    ) -> DocumentResponse | None:
        allowed_fields = {
            "title",
            "description",
            "category_id",
            "visibility",
            "status",
        }
        assignments = []
        params: dict[str, Any] = {"document_id": document_id}
        for field, value in fields.items():
            if field not in allowed_fields:
                continue
            if field == "status":
                assignments.append("status = CAST(:status AS document_status)")
                params[field] = _value(value)
                if value == DocumentStatus.PUBLISHED:
                    assignments.append("published_at = COALESCE(published_at, now())")
            elif field == "visibility":
                assignments.append("visibility = :visibility")
                params[field] = _value(value)
            else:
                assignments.append(f"{field} = :{field}")
                params[field] = _value(value)

        if not assignments:
            return await self.get_document(document_id)

        assignments.append("updated_at = now()")
        result = await self.db.execute(
            text(
                f"""
                UPDATE documents
                SET {", ".join(assignments)}
                WHERE id = :document_id
                  AND deleted_at IS NULL
                RETURNING id
                """
            ),
            params,
        )
        if result.scalar_one_or_none() is None:
            return None
        return await self._get_document(document_id, include_deleted=True)

    async def archive_document(self, document_id: UUID) -> DocumentResponse | None:
        result = await self.db.execute(
            text(
                """
                UPDATE documents
                SET status = 'ARCHIVED',
                    deleted_at = now(),
                    updated_at = now()
                WHERE id = :document_id
                  AND deleted_at IS NULL
                RETURNING id
                """
            ),
            {"document_id": document_id},
        )
        if result.scalar_one_or_none() is None:
            return None
        return await self._get_document(document_id, include_deleted=True)

    async def get_request_context(
        self,
        request_id: UUID,
    ) -> RequestAttachmentContext | None:
        result = await self.db.execute(
            text(
                """
                SELECT id, requester_id, status
                FROM requests
                WHERE id = :request_id
                  AND deleted_at IS NULL
                """
            ),
            {"request_id": request_id},
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return RequestAttachmentContext(
            request_id=UUID(str(row["id"])),
            requester_id=UUID(str(row["requester_id"])),
            status=_normalize_request_status(row["status"]),
        )

    async def create_request_attachment(
        self,
        *,
        request_id: UUID,
        uploaded_by: UUID,
        stored_file: StoredFileMetadata,
    ) -> RequestAttachmentResponse:
        result = await self.db.execute(
            text(
                """
                INSERT INTO request_attachments (
                    request_id,
                    file_name,
                    file_url,
                    mime_type,
                    file_size_bytes,
                    uploaded_by
                )
                VALUES (
                    :request_id,
                    :file_name,
                    :file_url,
                    :mime_type,
                    :file_size_bytes,
                    :uploaded_by
                )
                RETURNING id
                """
            ),
            {
                "request_id": request_id,
                "file_name": stored_file.file_name,
                "file_url": stored_file.storage_key,
                "mime_type": stored_file.mime_type,
                "file_size_bytes": stored_file.file_size_bytes,
                "uploaded_by": uploaded_by,
            },
        )
        attachment_id = UUID(str(result.scalar_one()))
        created = await self.get_request_attachment(
            request_id=request_id,
            attachment_id=attachment_id,
        )
        if created is None:  # pragma: no cover - defensive guard.
            raise AppError(status_code=500, message="Error interno del servidor")
        return created

    async def list_request_attachments(
        self,
        request_id: UUID,
    ) -> list[RequestAttachmentResponse]:
        result = await self.db.execute(
            text(
                """
                SELECT
                    id,
                    request_id,
                    file_name,
                    file_url,
                    mime_type,
                    file_size_bytes,
                    uploaded_by,
                    created_at
                FROM request_attachments
                WHERE request_id = :request_id
                ORDER BY created_at ASC
                """
            ),
            {"request_id": request_id},
        )
        return [_attachment_from_row(row) for row in result.mappings()]

    async def get_request_attachment(
        self,
        *,
        request_id: UUID,
        attachment_id: UUID,
    ) -> RequestAttachmentResponse | None:
        result = await self.db.execute(
            text(
                """
                SELECT
                    id,
                    request_id,
                    file_name,
                    file_url,
                    mime_type,
                    file_size_bytes,
                    uploaded_by,
                    created_at
                FROM request_attachments
                WHERE id = :attachment_id
                  AND request_id = :request_id
                """
            ),
            {"request_id": request_id, "attachment_id": attachment_id},
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _attachment_from_row(row)

    async def commit(self) -> None:
        await self.db.commit()

    async def rollback(self) -> None:
        await self.db.rollback()


class DocumentService:
    def __init__(
        self,
        repository: DocumentRepository,
        storage: LocalFileStorage,
        auditor: AdministrativeAuditor | None = None,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.auditor = auditor

    async def list_documents(
        self,
        *,
        current_user: UserPrincipal | None,
        status: DocumentStatus | None,
        visibility: DocumentVisibility | None,
        category_id: UUID | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[DocumentResponse]:
        is_admin = _has_documents_manage(current_user)
        if not is_admin and (status is not None or visibility is not None or category_id is not None):
            _raise_forbidden()
        documents = await self.repository.list_documents(
            public_only=not is_admin,
            status=status if is_admin else None,
            visibility=visibility if is_admin else None,
            category_id=category_id if is_admin else None,
            limit=limit,
            offset=offset,
        )
        return documents.model_copy(
            update={"items": [self._hydrate_document_metadata(item) for item in documents.items]}
        )

    async def get_document(
        self,
        *,
        current_user: UserPrincipal | None,
        document_id: UUID,
    ) -> DocumentResponse:
        document = await self._get_existing_document(document_id)
        self._ensure_can_view_document(document, current_user)
        return self._hydrate_document_metadata(document)

    async def create_document(
        self,
        *,
        actor: UserPrincipal,
        payload: DocumentCreateRequest,
        file: UploadedFilePayload,
    ) -> DocumentResponse:
        await self._ensure_category_exists(payload.category_id)
        stored_file: StoredFileMetadata | None = None
        try:
            stored_file = self.storage.store(file, bucket=_document_storage_bucket(payload))
            created = await self.repository.create_document_with_version(
                owner_id=actor.id,
                payload=payload,
                stored_file=stored_file,
            )
            await self._record_admin_action(
                actor_id=actor.id,
                entity_type="documents",
                entity_id=created.id,
                metadata={
                    "action": "document.created",
                    "status": payload.status.value,
                    "visibility": payload.visibility.value,
                    "mime_type": stored_file.mime_type,
                    "file_size_bytes": stored_file.file_size_bytes,
                    "sha256": stored_file.sha256,
                },
            )
            await self.repository.commit()
            return self._hydrate_document_metadata(created)
        except Exception:
            await self.repository.rollback()
            if stored_file is not None:
                self.storage.remove_uncommitted(stored_file.storage_key)
            raise

    async def update_document(
        self,
        *,
        actor: UserPrincipal,
        document_id: UUID,
        payload: DocumentUpdateRequest,
    ) -> DocumentResponse:
        existing = await self._get_existing_document(document_id)
        fields = payload.model_dump(exclude_unset=True)
        _ensure_update_fields(fields)
        await self._ensure_category_exists(fields.get("category_id"))

        try:
            updated = await self.repository.update_document(
                document_id=existing.id,
                fields=fields,
            )
            if updated is None:
                raise AppError(status_code=404, message="Documento no encontrado")
            await self._record_admin_action(
                actor_id=actor.id,
                entity_type="documents",
                entity_id=existing.id,
                metadata={
                    "action": "document.updated",
                    "changed_fields": sorted(fields),
                },
            )
            await self.repository.commit()
            return self._hydrate_document_metadata(updated)
        except Exception:
            await self.repository.rollback()
            raise

    async def delete_document(
        self,
        *,
        actor: UserPrincipal,
        document_id: UUID,
    ) -> DocumentResponse:
        existing = await self._get_existing_document(document_id)
        try:
            archived = await self.repository.archive_document(existing.id)
            if archived is None:
                raise AppError(status_code=404, message="Documento no encontrado")
            await self._record_admin_action(
                actor_id=actor.id,
                entity_type="documents",
                entity_id=existing.id,
                metadata={"action": "document.archived"},
            )
            await self.repository.commit()
            return self._hydrate_document_metadata(archived)
        except Exception:
            await self.repository.rollback()
            raise

    async def download_document(
        self,
        *,
        current_user: UserPrincipal | None,
        document_id: UUID,
    ) -> DownloadFileDescriptor:
        document = await self.get_document(
            current_user=current_user,
            document_id=document_id,
        )
        if document.latest_version is None:
            raise AppError(status_code=404, message="Archivo no encontrado")
        return self._download_descriptor(
            storage_key=document.latest_version.storage_key,
            file_name=document.latest_version.file_name,
            mime_type=document.latest_version.mime_type,
        )

    async def upload_request_attachment(
        self,
        *,
        actor: UserPrincipal,
        request_id: UUID,
        file: UploadedFilePayload,
    ) -> RequestAttachmentResponse:
        context = await self._get_visible_request_context(
            actor=actor,
            request_id=request_id,
        )
        _ensure_request_accepts_attachments(context.status)
        stored_file: StoredFileMetadata | None = None
        try:
            stored_file = self.storage.store(
                file,
                bucket=f"private/request-attachments/{request_id}",
            )
            attachment = await self.repository.create_request_attachment(
                request_id=request_id,
                uploaded_by=actor.id,
                stored_file=stored_file,
            )
            if _has_requests_manage(actor):
                await self._record_admin_action(
                    actor_id=actor.id,
                    entity_type="requests",
                    entity_id=request_id,
                    metadata={
                        "action": "request.attachment.created",
                        "attachment_id": str(attachment.id),
                        "mime_type": stored_file.mime_type,
                        "file_size_bytes": stored_file.file_size_bytes,
                        "sha256": stored_file.sha256,
                    },
                )
            await self.repository.commit()
            return self._hydrate_attachment_metadata(attachment)
        except Exception:
            await self.repository.rollback()
            if stored_file is not None:
                self.storage.remove_uncommitted(stored_file.storage_key)
            raise

    async def list_request_attachments(
        self,
        *,
        actor: UserPrincipal,
        request_id: UUID,
    ) -> list[RequestAttachmentResponse]:
        await self._get_visible_request_context(actor=actor, request_id=request_id)
        attachments = await self.repository.list_request_attachments(request_id)
        return [self._hydrate_attachment_metadata(item) for item in attachments]

    async def download_request_attachment(
        self,
        *,
        actor: UserPrincipal,
        request_id: UUID,
        attachment_id: UUID,
    ) -> DownloadFileDescriptor:
        await self._get_visible_request_context(actor=actor, request_id=request_id)
        attachment = await self.repository.get_request_attachment(
            request_id=request_id,
            attachment_id=attachment_id,
        )
        if attachment is None:
            raise AppError(status_code=404, message="Adjunto no encontrado")
        return self._download_descriptor(
            storage_key=attachment.storage_key,
            file_name=attachment.file_name,
            mime_type=attachment.mime_type,
        )

    async def _ensure_category_exists(self, category_id: UUID | None) -> None:
        if category_id is None:
            return
        if await self.repository.category_exists(category_id):
            return
        raise AppError(
            status_code=422,
            message="Categoria invalida",
            errors=[
                ErrorDetail(
                    field="category_id",
                    detail="La categoria no existe o no esta activa",
                )
            ],
        )

    async def _get_existing_document(self, document_id: UUID) -> DocumentResponse:
        document = await self.repository.get_document(document_id)
        if document is None:
            raise AppError(status_code=404, message="Documento no encontrado")
        return document

    def _ensure_can_view_document(
        self,
        document: DocumentResponse,
        current_user: UserPrincipal | None,
    ) -> None:
        if _is_public_document(document) or _has_documents_manage(current_user):
            return
        if current_user is None:
            raise AppError(status_code=401, message="No autenticado")
        _raise_forbidden()

    async def _get_visible_request_context(
        self,
        *,
        actor: UserPrincipal,
        request_id: UUID,
    ) -> RequestAttachmentContext:
        context = await self.repository.get_request_context(request_id)
        if context is None:
            raise AppError(status_code=404, message="Solicitud no encontrada")
        if context.requester_id == actor.id or _has_requests_manage(actor):
            return context
        raise AppError(status_code=404, message="Solicitud no encontrada")

    def _download_descriptor(
        self,
        *,
        storage_key: str,
        file_name: str,
        mime_type: str,
    ) -> DownloadFileDescriptor:
        path = self.storage.resolve_path(storage_key)
        if not path.exists():
            raise AppError(status_code=404, message="Archivo no encontrado")
        return DownloadFileDescriptor(path=path, file_name=file_name, mime_type=mime_type)

    def _hydrate_document_metadata(self, document: DocumentResponse) -> DocumentResponse:
        version = document.latest_version
        if version is None:
            return document
        metadata = self.storage.get_metadata(version.storage_key)
        if metadata is None:
            return document
        return document.model_copy(
            update={
                "latest_version": version.model_copy(update={"sha256": metadata.sha256})
            }
        )

    def _hydrate_attachment_metadata(
        self,
        attachment: RequestAttachmentResponse,
    ) -> RequestAttachmentResponse:
        metadata = self.storage.get_metadata(attachment.storage_key)
        if metadata is None:
            return attachment
        return attachment.model_copy(update={"sha256": metadata.sha256})

    async def _record_admin_action(
        self,
        *,
        actor_id: UUID,
        entity_type: str,
        entity_id: UUID,
        metadata: dict[str, object],
    ) -> None:
        if self.auditor is None:
            return
        await self.auditor.record_administrative_action(
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata,
        )


def create_document_service(db: AsyncSession, settings: Settings) -> DocumentService:
    return DocumentService(
        DatabaseDocumentRepository(db),
        LocalFileStorage(settings),
        AuditService(db),
    )


def _value(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    return value


def _document_where(
    *,
    public_only: bool,
    status: DocumentStatus | None,
    visibility: DocumentVisibility | None,
    category_id: UUID | None,
) -> tuple[str, dict[str, Any]]:
    params: dict[str, Any] = {}
    conditions = ["d.deleted_at IS NULL"]
    if public_only:
        conditions.append("d.status = 'PUBLISHED'")
        conditions.append("d.visibility = 'PUBLIC'")
        return " AND ".join(conditions), params
    if status is not None:
        conditions.append("d.status = CAST(:status AS document_status)")
        params["status"] = status.value
    if visibility is not None:
        conditions.append("d.visibility = :visibility")
        params["visibility"] = visibility.value
    if category_id is not None:
        conditions.append("d.category_id = :category_id")
        params["category_id"] = category_id
    return " AND ".join(conditions), params


def _document_storage_bucket(payload: DocumentCreateRequest) -> str:
    if payload.status == DocumentStatus.PUBLISHED and payload.visibility == DocumentVisibility.PUBLIC:
        return "public/documents"
    return "private/documents"


def _is_public_document(document: DocumentResponse) -> bool:
    return (
        document.status == DocumentStatus.PUBLISHED
        and document.visibility == DocumentVisibility.PUBLIC
    )


def _has_documents_manage(current_user: UserPrincipal | None) -> bool:
    return (
        current_user is not None
        and PermissionCode.DOCUMENTS_MANAGE.value in set(current_user.permissions)
    )


def _has_requests_manage(current_user: UserPrincipal) -> bool:
    return PermissionCode.REQUESTS_MANAGE.value in set(current_user.permissions)


def _raise_forbidden() -> None:
    raise AppError(
        status_code=403,
        message="Permisos insuficientes",
        errors=[
            ErrorDetail(
                field="permissions",
                detail="Permiso requerido no presente",
            )
        ],
    )


def _ensure_update_fields(fields: dict[str, Any]) -> None:
    if fields:
        return
    raise AppError(status_code=422, message="No hay campos para actualizar")


def _ensure_request_accepts_attachments(status: RequestStatus) -> None:
    if status not in {
        RequestStatus.CLOSED,
        RequestStatus.APPROVED,
        RequestStatus.REJECTED,
    }:
        return
    raise AppError(status_code=409, message="Solicitud no admite adjuntos")


def _normalize_document_status(value: object) -> DocumentStatus:
    return DocumentStatus(str(value).split(".")[-1].upper())


def _normalize_visibility(value: object) -> DocumentVisibility:
    return DocumentVisibility(str(value).split(".")[-1].upper())


def _normalize_request_status(value: object) -> RequestStatus:
    return RequestStatus(str(value).split(".")[-1].upper())


def _document_from_row(row: Any) -> DocumentResponse:
    document_id = UUID(str(row["id"]))
    latest_version = None
    if row["version_id"] is not None:
        latest_version = DocumentVersionResponse(
            id=UUID(str(row["version_id"])),
            document_id=document_id,
            version_number=int(row["version_number"]),
            file_name=str(row["file_name"]),
            storage_key=str(row["file_url"]),
            mime_type=str(row["mime_type"]),
            file_size_bytes=int(row["file_size_bytes"]),
            uploaded_by=UUID(str(row["uploaded_by"])) if row["uploaded_by"] else None,
            changelog=row["changelog"],
            created_at=row["version_created_at"],
        )
    return DocumentResponse(
        id=document_id,
        category_id=UUID(str(row["category_id"])) if row["category_id"] else None,
        category_name=row["category_name"],
        category_slug=row["category_slug"],
        title=str(row["title"]),
        description=row["description"],
        visibility=_normalize_visibility(row["visibility"]),
        status=_normalize_document_status(row["status"]),
        owner_id=UUID(str(row["owner_id"])) if row["owner_id"] else None,
        owner_name=row["owner_name"],
        published_at=row["published_at"],
        latest_version=latest_version,
        download_url=f"/api/v1/documents/{document_id}/download",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _attachment_from_row(row: Any) -> RequestAttachmentResponse:
    request_id = UUID(str(row["request_id"]))
    attachment_id = UUID(str(row["id"]))
    return RequestAttachmentResponse(
        id=attachment_id,
        request_id=request_id,
        file_name=str(row["file_name"]),
        storage_key=str(row["file_url"]),
        mime_type=str(row["mime_type"]),
        file_size_bytes=int(row["file_size_bytes"]),
        uploaded_by=UUID(str(row["uploaded_by"])) if row["uploaded_by"] else None,
        created_at=row["created_at"],
        download_url=(
            f"/api/v1/requests/{request_id}/attachments/{attachment_id}/download"
        ),
    )


_DOCUMENT_SELECT = """
SELECT
    d.id,
    d.category_id,
    c.name AS category_name,
    c.slug AS category_slug,
    d.title,
    d.description,
    d.visibility,
    d.status,
    d.owner_id,
    owner.name AS owner_name,
    d.published_at,
    d.created_at,
    d.updated_at,
    v.id AS version_id,
    v.version_number,
    v.file_name,
    v.file_url,
    v.mime_type,
    v.file_size_bytes,
    v.uploaded_by,
    v.changelog,
    v.created_at AS version_created_at
FROM documents d
LEFT JOIN document_categories c ON c.id = d.category_id
LEFT JOIN users owner ON owner.id = d.owner_id
LEFT JOIN LATERAL (
    SELECT
        id,
        version_number,
        file_name,
        file_url,
        mime_type,
        file_size_bytes,
        uploaded_by,
        changelog,
        created_at
    FROM document_versions
    WHERE document_id = d.id
    ORDER BY version_number DESC
    LIMIT 1
) v ON TRUE
"""
