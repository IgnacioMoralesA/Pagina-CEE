from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from app.backend.auth.dependencies import get_auth_context_validator
from app.backend.auth.jwt import create_access_token
from app.backend.auth.permissions import PermissionCode, RoleCode
from app.backend.auth.schemas import TokenClaims, UserPrincipal
from app.backend.core.config import Settings
from app.backend.core.errors import AppError
from app.backend.documents.dependencies import get_document_service
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
from app.backend.documents.service import (
    DocumentService,
    RequestAttachmentContext,
)
from app.backend.files.multipart import parse_multipart_upload
from app.backend.files.storage import LocalFileStorage, StoredFileMetadata
from app.backend.main import create_app
from app.backend.student_requests.schemas import RequestStatus


class StaticAuthContextValidator:
    def __init__(
        self,
        *,
        roles: list[RoleCode] | None = None,
        permissions: list[str] | None = None,
    ) -> None:
        self.roles = roles or [RoleCode.STUDENT]
        self.permissions = permissions or []

    async def validate(self, _: str, claims: TokenClaims) -> UserPrincipal:
        return UserPrincipal(
            id=claims.user_id,
            session_id=claims.session_id,
            email=claims.email,
            name=claims.name,
            role=self.roles[0],
            roles=self.roles,
            permissions=self.permissions,
        )


class RecordingAuditor:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    async def record_administrative_action(
        self,
        *,
        actor_id: UUID,
        entity_type: str,
        entity_id: UUID | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.events.append(
            {
                "actor_id": actor_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "metadata": metadata or {},
            }
        )


class StreamingRequestWithoutContentLength:
    def __init__(self, chunks: list[bytes]) -> None:
        self.headers = {
            "content-type": "multipart/form-data; boundary=test-boundary",
        }
        self._chunks = chunks

    async def stream(self):
        for chunk in self._chunks:
            yield chunk


class FakeDocumentRepository:
    def __init__(
        self,
        *,
        documents: list[DocumentResponse] | None = None,
        request_contexts: dict[UUID, RequestAttachmentContext] | None = None,
        category_exists: bool = True,
    ) -> None:
        self.documents = {item.id: item for item in documents or []}
        self.request_contexts = request_contexts or {}
        self.attachments: dict[UUID, RequestAttachmentResponse] = {}
        self.deleted_document_ids: set[UUID] = set()
        self.category_exists_value = category_exists
        self.committed = False
        self.rolled_back = False

    async def category_exists(self, category_id: UUID) -> bool:
        return self.category_exists_value

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
        items = [
            item
            for item in self.documents.values()
            if item.id not in self.deleted_document_ids
            and (
                not public_only
                or (
                    item.status == DocumentStatus.PUBLISHED
                    and item.visibility == DocumentVisibility.PUBLIC
                )
            )
            and (status is None or item.status == status)
            and (visibility is None or item.visibility == visibility)
            and (category_id is None or item.category_id == category_id)
        ]
        return PaginatedResponse[DocumentResponse](
            items=items[offset : offset + limit],
            total=len(items),
            limit=limit,
            offset=offset,
        )

    async def get_document(self, document_id: UUID) -> DocumentResponse | None:
        if document_id in self.deleted_document_ids:
            return None
        return self.documents.get(document_id)

    async def create_document_with_version(
        self,
        *,
        owner_id: UUID,
        payload: DocumentCreateRequest,
        stored_file: StoredFileMetadata,
    ) -> DocumentResponse:
        document_id = uuid4()
        now = datetime.now(timezone.utc)
        document = DocumentResponse(
            id=document_id,
            title=payload.title,
            description=payload.description,
            category_id=payload.category_id,
            category_name=None,
            category_slug=None,
            visibility=payload.visibility,
            status=payload.status,
            owner_id=owner_id,
            owner_name="Usuario Demo",
            published_at=now if payload.status == DocumentStatus.PUBLISHED else None,
            created_at=now,
            updated_at=now,
            download_url=f"/api/v1/documents/{document_id}/download",
            latest_version=DocumentVersionResponse(
                id=uuid4(),
                document_id=document_id,
                version_number=1,
                file_name=stored_file.file_name,
                storage_key=stored_file.storage_key,
                mime_type=stored_file.mime_type,
                file_size_bytes=stored_file.file_size_bytes,
                uploaded_by=owner_id,
                created_at=now,
            ),
        )
        self.documents[document_id] = document
        return document

    async def update_document(
        self,
        *,
        document_id: UUID,
        fields: dict[str, object],
    ) -> DocumentResponse | None:
        document = self.documents.get(document_id)
        if document is None or document_id in self.deleted_document_ids:
            return None
        update = dict(fields)
        if update.get("status") == DocumentStatus.PUBLISHED and document.published_at is None:
            update["published_at"] = datetime.now(timezone.utc)
        updated = document.model_copy(update=update)
        self.documents[document_id] = updated
        return updated

    async def archive_document(self, document_id: UUID) -> DocumentResponse | None:
        document = self.documents.get(document_id)
        if document is None or document_id in self.deleted_document_ids:
            return None
        updated = document.model_copy(update={"status": DocumentStatus.ARCHIVED})
        self.documents[document_id] = updated
        self.deleted_document_ids.add(document_id)
        return updated

    async def get_request_context(
        self,
        request_id: UUID,
    ) -> RequestAttachmentContext | None:
        return self.request_contexts.get(request_id)

    async def create_request_attachment(
        self,
        *,
        request_id: UUID,
        uploaded_by: UUID,
        stored_file: StoredFileMetadata,
    ) -> RequestAttachmentResponse:
        attachment_id = uuid4()
        attachment = RequestAttachmentResponse(
            id=attachment_id,
            request_id=request_id,
            file_name=stored_file.file_name,
            storage_key=stored_file.storage_key,
            mime_type=stored_file.mime_type,
            file_size_bytes=stored_file.file_size_bytes,
            uploaded_by=uploaded_by,
            created_at=datetime.now(timezone.utc),
            download_url=(
                f"/api/v1/requests/{request_id}/attachments/"
                f"{attachment_id}/download"
            ),
        )
        self.attachments[attachment_id] = attachment
        return attachment

    async def list_request_attachments(
        self,
        request_id: UUID,
    ) -> list[RequestAttachmentResponse]:
        return [
            item for item in self.attachments.values() if item.request_id == request_id
        ]

    async def get_request_attachment(
        self,
        *,
        request_id: UUID,
        attachment_id: UUID,
    ) -> RequestAttachmentResponse | None:
        attachment = self.attachments.get(attachment_id)
        if attachment is None or attachment.request_id != request_id:
            return None
        return attachment

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def build_document(
    document_id: UUID,
    *,
    status: DocumentStatus = DocumentStatus.PUBLISHED,
    visibility: DocumentVisibility = DocumentVisibility.PUBLIC,
    title: str = "Acta publica",
) -> DocumentResponse:
    now = datetime.now(timezone.utc)
    return DocumentResponse(
        id=document_id,
        title=title,
        description="Documento de prueba",
        category_id=None,
        category_name=None,
        category_slug=None,
        visibility=visibility,
        status=status,
        owner_id=uuid4(),
        owner_name="Directiva",
        published_at=now if status == DocumentStatus.PUBLISHED else None,
        created_at=now,
        updated_at=now,
        download_url=f"/api/v1/documents/{document_id}/download",
        latest_version=DocumentVersionResponse(
            id=uuid4(),
            document_id=document_id,
            version_number=1,
            file_name="acta.pdf",
            storage_key=f"public/documents/{document_id.hex}.pdf",
            mime_type="application/pdf",
            file_size_bytes=12,
            uploaded_by=uuid4(),
            created_at=now,
        ),
    )


def build_service(
    tmp_path: Path,
    *,
    documents: list[DocumentResponse] | None = None,
    request_contexts: dict[UUID, RequestAttachmentContext] | None = None,
    max_upload_size_bytes: int = 10 * 1024 * 1024,
) -> tuple[DocumentService, FakeDocumentRepository, RecordingAuditor]:
    settings = Settings(
        jwt_secret_key="unit-test-secret",
        file_storage_path=str(tmp_path),
        max_upload_size_bytes=max_upload_size_bytes,
    )
    repository = FakeDocumentRepository(
        documents=documents,
        request_contexts=request_contexts,
    )
    auditor = RecordingAuditor()
    return DocumentService(repository, LocalFileStorage(settings), auditor), repository, auditor


def build_client(
    service: DocumentService,
    *,
    permissions: list[str] | None = None,
    user_id: UUID | None = None,
    tmp_path: Path,
    max_upload_size_bytes: int = 10 * 1024 * 1024,
) -> tuple[TestClient, str, UUID]:
    settings = Settings(
        jwt_secret_key="unit-test-secret",
        file_storage_path=str(tmp_path),
        max_upload_size_bytes=max_upload_size_bytes,
    )
    resolved_user_id = user_id or uuid4()
    app = create_app(settings)
    app.dependency_overrides[get_document_service] = lambda: service
    app.dependency_overrides[get_auth_context_validator] = lambda: (
        StaticAuthContextValidator(permissions=permissions or [])
    )
    token, _ = create_access_token(
        user_id=resolved_user_id,
        session_id=uuid4(),
        email="usuario@example.edu",
        name="Usuario Demo",
        roles=[RoleCode.STUDENT],
        permissions=[],
        settings=settings,
    )
    return TestClient(app), token, resolved_user_id


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def pdf_upload(
    filename: str = "acta.pdf",
    content: bytes = b"%PDF-1.4 demo",
    mime_type: str = "application/pdf",
) -> dict[str, tuple[str, bytes, str]]:
    return {"file": (filename, content, mime_type)}


def office_archive(prefix: str) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr(f"{prefix}/document.xml", "<document />")
    return buffer.getvalue()


def assert_standard_response_shape(payload: dict[str, object]) -> None:
    assert set(payload) == {"data", "message", "errors"}


def test_public_user_lists_only_public_documents(tmp_path: Path) -> None:
    public = build_document(uuid4(), title="Publico")
    private = build_document(
        uuid4(),
        title="Privado",
        visibility=DocumentVisibility.PRIVATE,
    )
    draft = build_document(uuid4(), title="Borrador", status=DocumentStatus.DRAFT)
    service, _, _ = build_service(tmp_path, documents=[public, private, draft])
    client, _, _ = build_client(service, tmp_path=tmp_path)

    response = client.get("/api/v1/documents")

    assert response.status_code == 200
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["data"]["total"] == 1
    assert payload["data"]["items"][0]["id"] == str(public.id)


def test_public_user_cannot_download_private_document(tmp_path: Path) -> None:
    private = build_document(uuid4(), visibility=DocumentVisibility.PRIVATE)
    service, _, _ = build_service(tmp_path, documents=[private])
    client, _, _ = build_client(service, tmp_path=tmp_path)

    response = client.get(f"/api/v1/documents/{private.id}/download")

    assert response.status_code == 401
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "No autenticado"


def test_authenticated_user_without_permission_cannot_view_or_download_private_document(
    tmp_path: Path,
) -> None:
    service, _, _ = build_service(tmp_path)
    admin_client, admin_token, _ = build_client(
        service,
        permissions=[PermissionCode.DOCUMENTS_MANAGE.value],
        tmp_path=tmp_path,
    )
    create_response = admin_client.post(
        "/api/v1/documents",
        headers=auth_header(admin_token),
        data={"title": "Privado", "visibility": "PRIVATE"},
        files=pdf_upload(),
    )
    document_id = create_response.json()["data"]["id"]
    user_client, user_token, _ = build_client(service, tmp_path=tmp_path)

    detail_response = user_client.get(
        f"/api/v1/documents/{document_id}",
        headers=auth_header(user_token),
    )
    download_response = user_client.get(
        f"/api/v1/documents/{document_id}/download",
        headers=auth_header(user_token),
    )

    assert detail_response.status_code == 403
    assert_standard_response_shape(detail_response.json())
    assert download_response.status_code == 403
    assert_standard_response_shape(download_response.json())


def test_user_with_documents_manage_can_view_and_download_private_document(
    tmp_path: Path,
) -> None:
    service, _, _ = build_service(tmp_path)
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.DOCUMENTS_MANAGE.value],
        tmp_path=tmp_path,
    )
    create_response = client.post(
        "/api/v1/documents",
        headers=auth_header(token),
        data={"title": "Privado", "visibility": "PRIVATE"},
        files=pdf_upload(content=b"%PDF-1.4 privado"),
    )
    document_id = create_response.json()["data"]["id"]

    detail_response = client.get(
        f"/api/v1/documents/{document_id}",
        headers=auth_header(token),
    )
    download_response = client.get(
        f"/api/v1/documents/{document_id}/download",
        headers=auth_header(token),
    )

    assert detail_response.status_code == 200
    assert_standard_response_shape(detail_response.json())
    assert download_response.status_code == 200
    assert download_response.content == b"%PDF-1.4 privado"


def test_document_filters_require_documents_manage(tmp_path: Path) -> None:
    public = build_document(uuid4(), title="Publico")
    draft = build_document(uuid4(), title="Borrador", status=DocumentStatus.DRAFT)
    service, _, _ = build_service(tmp_path, documents=[public, draft])
    user_client, user_token, _ = build_client(service, tmp_path=tmp_path)
    admin_client, admin_token, _ = build_client(
        service,
        permissions=[PermissionCode.DOCUMENTS_MANAGE.value],
        tmp_path=tmp_path,
    )

    forbidden_response = user_client.get(
        "/api/v1/documents?status=DRAFT",
        headers=auth_header(user_token),
    )
    allowed_response = admin_client.get(
        "/api/v1/documents?status=DRAFT",
        headers=auth_header(admin_token),
    )

    assert forbidden_response.status_code == 403
    assert_standard_response_shape(forbidden_response.json())
    assert allowed_response.status_code == 200
    assert allowed_response.json()["data"]["total"] == 1
    assert allowed_response.json()["data"]["items"][0]["id"] == str(draft.id)


def test_user_with_documents_manage_can_upload_document(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path)
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.DOCUMENTS_MANAGE.value],
        tmp_path=tmp_path,
    )

    response = client.post(
        "/api/v1/documents",
        headers=auth_header(token),
        data={"title": "Acta junio", "status": "PUBLISHED"},
        files=pdf_upload(),
    )

    assert response.status_code == 201
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Documento creado"
    assert payload["data"]["title"] == "Acta junio"
    assert payload["data"]["latest_version"]["file_name"] == "acta.pdf"
    assert "storage_key" not in payload["data"]["latest_version"]
    assert "file_url" not in payload["data"]["latest_version"]


@pytest.mark.parametrize(
    ("filename", "content", "mime_type"),
    [
        ("documento.pdf", b"%PDF-1.7 valido", "application/pdf"),
        ("imagen.png", b"\x89PNG\r\n\x1a\nvalido", "image/png"),
        ("foto.jpg", b"\xff\xd8\xffvalido", "image/jpeg"),
        (
            "documento.docx",
            office_archive("word"),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        (
            "planilla.xlsx",
            office_archive("xl"),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        ("datos.csv", b"nombre,valor\nuno,1\n", "text/csv"),
    ],
)
def test_all_allowed_file_types_are_accepted(
    tmp_path: Path,
    filename: str,
    content: bytes,
    mime_type: str,
) -> None:
    service, _, _ = build_service(tmp_path)
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.DOCUMENTS_MANAGE.value],
        tmp_path=tmp_path,
    )

    response = client.post(
        "/api/v1/documents",
        headers=auth_header(token),
        data={"title": filename},
        files={"file": (filename, content, mime_type)},
    )

    assert response.status_code == 201
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["data"]["latest_version"]["file_name"] == filename
    assert payload["data"]["latest_version"]["sha256"] == hashlib.sha256(
        content
    ).hexdigest()


def test_uploaded_document_calculates_sha256(tmp_path: Path) -> None:
    content = b"%PDF-1.4 contenido"
    service, _, _ = build_service(tmp_path)
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.DOCUMENTS_MANAGE.value],
        tmp_path=tmp_path,
    )

    response = client.post(
        "/api/v1/documents",
        headers=auth_header(token),
        data={"title": "Hash"},
        files=pdf_upload(content=content),
    )

    assert response.status_code == 201
    assert response.json()["data"]["latest_version"]["sha256"] == (
        hashlib.sha256(content).hexdigest()
    )


def test_uploaded_document_uses_unique_uuid_storage_names(tmp_path: Path) -> None:
    service, repository, _ = build_service(tmp_path)
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.DOCUMENTS_MANAGE.value],
        tmp_path=tmp_path,
    )

    for title in ("Primero", "Segundo"):
        response = client.post(
            "/api/v1/documents",
            headers=auth_header(token),
            data={"title": title},
            files=pdf_upload(filename="mismo-nombre.pdf"),
        )
        assert response.status_code == 201

    storage_keys = [
        document.latest_version.storage_key
        for document in repository.documents.values()
        if document.latest_version is not None
    ]

    assert len(storage_keys) == 2
    assert len(set(storage_keys)) == 2
    for storage_key in storage_keys:
        assert Path(storage_key).parent.as_posix() == "private/documents"
        UUID(Path(storage_key).stem)
        assert (tmp_path / storage_key).exists()


def test_upload_document_records_audit(tmp_path: Path) -> None:
    service, _, auditor = build_service(tmp_path)
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.DOCUMENTS_MANAGE.value],
        tmp_path=tmp_path,
    )

    response = client.post(
        "/api/v1/documents",
        headers=auth_header(token),
        data={"title": "Auditado"},
        files=pdf_upload(),
    )

    assert response.status_code == 201
    assert auditor.events[0]["entity_type"] == "documents"
    assert auditor.events[0]["metadata"]["action"] == "document.created"


def test_user_without_documents_permission_cannot_upload_document(
    tmp_path: Path,
) -> None:
    service, _, _ = build_service(tmp_path)
    client, token, _ = build_client(service, permissions=[], tmp_path=tmp_path)

    response = client.post(
        "/api/v1/documents",
        headers=auth_header(token),
        data={"title": "Sin permiso"},
        files=pdf_upload(),
    )

    assert response.status_code == 403
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Permisos insuficientes"


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        (
            "post",
            "/api/v1/documents",
            {"data": {"title": "Sin sesion"}, "files": pdf_upload()},
        ),
        ("patch", "/api/v1/documents/{document_id}", {"json": {"title": "Cambio"}}),
        ("delete", "/api/v1/documents/{document_id}", {}),
    ],
)
def test_administrative_document_routes_require_session(
    tmp_path: Path,
    method: str,
    path: str,
    kwargs: dict[str, object],
) -> None:
    document = build_document(uuid4())
    service, _, _ = build_service(tmp_path, documents=[document])
    client, _, _ = build_client(service, tmp_path=tmp_path)

    response = getattr(client, method)(
        path.format(document_id=document.id),
        **kwargs,
    )

    assert response.status_code == 401
    assert_standard_response_shape(response.json())


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_patch_and_delete_require_documents_manage(
    tmp_path: Path,
    method: str,
) -> None:
    document = build_document(uuid4())
    service, _, _ = build_service(tmp_path, documents=[document])
    client, token, _ = build_client(service, tmp_path=tmp_path)
    kwargs = {"json": {"title": "Cambio"}} if method == "patch" else {}

    response = getattr(client, method)(
        f"/api/v1/documents/{document.id}",
        headers=auth_header(token),
        **kwargs,
    )

    assert response.status_code == 403
    assert_standard_response_shape(response.json())


def test_file_with_disallowed_type_is_rejected(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path)
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.DOCUMENTS_MANAGE.value],
        tmp_path=tmp_path,
    )

    response = client.post(
        "/api/v1/documents",
        headers=auth_header(token),
        data={"title": "No permitido"},
        files=pdf_upload("script.exe", b"boom", "application/octet-stream"),
    )

    assert response.status_code == 415
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Tipo de archivo no permitido"


def test_renamed_executable_with_pdf_mime_is_rejected(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path)
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.DOCUMENTS_MANAGE.value],
        tmp_path=tmp_path,
    )

    response = client.post(
        "/api/v1/documents",
        headers=auth_header(token),
        data={"title": "Malware"},
        files=pdf_upload("malware.pdf", b"MZ fake executable", "application/pdf"),
    )

    assert response.status_code == 415
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Contenido de archivo no coincide con tipo declarado"


def test_empty_file_is_rejected(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path)
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.DOCUMENTS_MANAGE.value],
        tmp_path=tmp_path,
    )

    response = client.post(
        "/api/v1/documents",
        headers=auth_header(token),
        data={"title": "Vacio"},
        files=pdf_upload(content=b""),
    )

    assert response.status_code == 422
    assert response.json()["message"] == "Archivo vacio"


def test_multipart_stream_without_content_length_is_limited() -> None:
    request = StreamingRequestWithoutContentLength([b"x" * (64 * 1024 + 2)])

    with pytest.raises(AppError) as exc_info:
        asyncio.run(parse_multipart_upload(request, max_file_size_bytes=1))

    assert exc_info.value.status_code == 413
    assert exc_info.value.message == "Archivo demasiado grande"


def test_file_larger_than_maximum_is_rejected(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path, max_upload_size_bytes=5)
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.DOCUMENTS_MANAGE.value],
        tmp_path=tmp_path,
        max_upload_size_bytes=5,
    )

    response = client.post(
        "/api/v1/documents",
        headers=auth_header(token),
        data={"title": "Grande"},
        files=pdf_upload(content=b"123456"),
    )

    assert response.status_code == 413
    assert response.json()["message"] == "Archivo demasiado grande"


def test_malicious_filename_does_not_affect_storage_path(tmp_path: Path) -> None:
    service, repository, _ = build_service(tmp_path)
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.DOCUMENTS_MANAGE.value],
        tmp_path=tmp_path,
    )

    response = client.post(
        "/api/v1/documents",
        headers=auth_header(token),
        data={"title": "Seguro"},
        files=pdf_upload("../secreto.pdf"),
    )

    assert response.status_code == 201
    document = next(iter(repository.documents.values()))
    assert document.latest_version is not None
    assert document.latest_version.file_name == "secreto.pdf"
    assert ".." not in document.latest_version.storage_key
    stored_path = tmp_path / document.latest_version.storage_key
    assert stored_path.resolve().is_relative_to(tmp_path.resolve())


def test_download_does_not_expose_internal_path(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path)
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.DOCUMENTS_MANAGE.value],
        tmp_path=tmp_path,
    )
    create_response = client.post(
        "/api/v1/documents",
        headers=auth_header(token),
        data={"title": "Descarga", "status": "PUBLISHED", "visibility": "PUBLIC"},
        files=pdf_upload(content=b"%PDF-1.4 descarga"),
    )
    document_id = create_response.json()["data"]["id"]

    response = client.get(f"/api/v1/documents/{document_id}/download")

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 descarga"
    content_disposition = response.headers["content-disposition"]
    assert "acta.pdf" in content_disposition
    assert str(tmp_path) not in content_disposition


def test_patch_updates_metadata_and_records_audit(tmp_path: Path) -> None:
    document = build_document(uuid4())
    service, _, auditor = build_service(tmp_path, documents=[document])
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.DOCUMENTS_MANAGE.value],
        tmp_path=tmp_path,
    )

    response = client.patch(
        f"/api/v1/documents/{document.id}",
        headers=auth_header(token),
        json={"title": "Titulo editado", "visibility": "PRIVATE"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["data"]["title"] == "Titulo editado"
    assert payload["data"]["visibility"] == "PRIVATE"
    assert auditor.events[0]["metadata"]["action"] == "document.updated"


def test_patch_to_published_assigns_published_at(tmp_path: Path) -> None:
    document = build_document(uuid4(), status=DocumentStatus.DRAFT)
    service, _, _ = build_service(tmp_path, documents=[document])
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.DOCUMENTS_MANAGE.value],
        tmp_path=tmp_path,
    )

    response = client.patch(
        f"/api/v1/documents/{document.id}",
        headers=auth_header(token),
        json={"status": "PUBLISHED"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "PUBLISHED"
    assert response.json()["data"]["published_at"] is not None


def test_invalid_document_category_is_rejected(tmp_path: Path) -> None:
    settings = Settings(
        jwt_secret_key="unit-test-secret",
        file_storage_path=str(tmp_path),
    )
    repository = FakeDocumentRepository(category_exists=False)
    service = DocumentService(
        repository,
        LocalFileStorage(settings),
        RecordingAuditor(),
    )
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.DOCUMENTS_MANAGE.value],
        tmp_path=tmp_path,
    )

    response = client.post(
        "/api/v1/documents",
        headers=auth_header(token),
        data={"title": "Categoria invalida", "category_id": str(uuid4())},
        files=pdf_upload(),
    )

    assert response.status_code == 422
    assert_standard_response_shape(response.json())
    assert response.json()["message"] == "Categoria invalida"


def test_delete_performs_logical_deletion(tmp_path: Path) -> None:
    document = build_document(uuid4())
    service, _, auditor = build_service(tmp_path, documents=[document])
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.DOCUMENTS_MANAGE.value],
        tmp_path=tmp_path,
    )

    delete_response = client.delete(
        f"/api/v1/documents/{document.id}",
        headers=auth_header(token),
    )
    list_response = client.get("/api/v1/documents")

    assert delete_response.status_code == 200
    assert delete_response.json()["data"]["status"] == "ARCHIVED"
    assert list_response.json()["data"]["total"] == 0
    assert auditor.events[0]["metadata"]["action"] == "document.archived"


def test_request_owner_can_attach_file(tmp_path: Path) -> None:
    request_id = uuid4()
    owner_id = uuid4()
    context = RequestAttachmentContext(
        request_id=request_id,
        requester_id=owner_id,
        status=RequestStatus.SUBMITTED,
    )
    service, _, _ = build_service(tmp_path, request_contexts={request_id: context})
    client, token, _ = build_client(service, user_id=owner_id, tmp_path=tmp_path)

    response = client.post(
        f"/api/v1/requests/{request_id}/attachments",
        headers=auth_header(token),
        files=pdf_upload(),
    )

    assert response.status_code == 201
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["data"]["sha256"] == hashlib.sha256(b"%PDF-1.4 demo").hexdigest()
    assert "storage_key" not in payload["data"]


def test_non_owner_cannot_attach_to_other_request(tmp_path: Path) -> None:
    request_id = uuid4()
    context = RequestAttachmentContext(
        request_id=request_id,
        requester_id=uuid4(),
        status=RequestStatus.SUBMITTED,
    )
    service, _, _ = build_service(tmp_path, request_contexts={request_id: context})
    client, token, _ = build_client(service, user_id=uuid4(), tmp_path=tmp_path)

    response = client.post(
        f"/api/v1/requests/{request_id}/attachments",
        headers=auth_header(token),
        files=pdf_upload(),
    )

    assert response.status_code == 404
    assert response.json()["message"] == "Solicitud no encontrada"


def test_user_with_requests_manage_can_attach_administratively(
    tmp_path: Path,
) -> None:
    request_id = uuid4()
    context = RequestAttachmentContext(
        request_id=request_id,
        requester_id=uuid4(),
        status=RequestStatus.SUBMITTED,
    )
    service, _, auditor = build_service(
        tmp_path,
        request_contexts={request_id: context},
    )
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.REQUESTS_MANAGE.value],
        tmp_path=tmp_path,
    )

    response = client.post(
        f"/api/v1/requests/{request_id}/attachments",
        headers=auth_header(token),
        files=pdf_upload(),
    )

    assert response.status_code == 201
    assert auditor.events[0]["entity_type"] == "requests"
    assert auditor.events[0]["metadata"]["action"] == "request.attachment.created"


@pytest.mark.parametrize(
    "status",
    [RequestStatus.CLOSED, RequestStatus.APPROVED, RequestStatus.REJECTED],
)
def test_cannot_attach_to_terminal_request(
    tmp_path: Path,
    status: RequestStatus,
) -> None:
    request_id = uuid4()
    owner_id = uuid4()
    context = RequestAttachmentContext(
        request_id=request_id,
        requester_id=owner_id,
        status=status,
    )
    service, _, _ = build_service(tmp_path, request_contexts={request_id: context})
    client, token, _ = build_client(service, user_id=owner_id, tmp_path=tmp_path)

    response = client.post(
        f"/api/v1/requests/{request_id}/attachments",
        headers=auth_header(token),
        files=pdf_upload(),
    )

    assert response.status_code == 409
    assert response.json()["message"] == "Solicitud no admite adjuntos"


def test_request_owner_can_list_and_download_attachments(tmp_path: Path) -> None:
    request_id = uuid4()
    owner_id = uuid4()
    context = RequestAttachmentContext(
        request_id=request_id,
        requester_id=owner_id,
        status=RequestStatus.SUBMITTED,
    )
    service, _, _ = build_service(tmp_path, request_contexts={request_id: context})
    client, token, _ = build_client(service, user_id=owner_id, tmp_path=tmp_path)
    create_response = client.post(
        f"/api/v1/requests/{request_id}/attachments",
        headers=auth_header(token),
        files=pdf_upload(content=b"%PDF-1.4 adjunto"),
    )
    attachment_id = create_response.json()["data"]["id"]

    list_response = client.get(
        f"/api/v1/requests/{request_id}/attachments",
        headers=auth_header(token),
    )
    download_response = client.get(
        f"/api/v1/requests/{request_id}/attachments/{attachment_id}/download",
        headers=auth_header(token),
    )

    assert list_response.status_code == 200
    assert_standard_response_shape(list_response.json())
    assert len(list_response.json()["data"]) == 1
    assert download_response.status_code == 200
    assert download_response.content == b"%PDF-1.4 adjunto"


def test_other_user_cannot_download_request_attachment(tmp_path: Path) -> None:
    request_id = uuid4()
    owner_id = uuid4()
    context = RequestAttachmentContext(
        request_id=request_id,
        requester_id=owner_id,
        status=RequestStatus.SUBMITTED,
    )
    service, _, _ = build_service(tmp_path, request_contexts={request_id: context})
    owner_client, owner_token, _ = build_client(
        service,
        user_id=owner_id,
        tmp_path=tmp_path,
    )
    create_response = owner_client.post(
        f"/api/v1/requests/{request_id}/attachments",
        headers=auth_header(owner_token),
        files=pdf_upload(),
    )
    attachment_id = create_response.json()["data"]["id"]
    other_client, other_token, _ = build_client(
        service,
        user_id=uuid4(),
        tmp_path=tmp_path,
    )

    response = other_client.get(
        f"/api/v1/requests/{request_id}/attachments/{attachment_id}/download",
        headers=auth_header(other_token),
    )

    assert response.status_code == 404
    assert response.json()["message"] == "Solicitud no encontrada"


def test_other_user_cannot_list_request_attachments(tmp_path: Path) -> None:
    request_id = uuid4()
    context = RequestAttachmentContext(
        request_id=request_id,
        requester_id=uuid4(),
        status=RequestStatus.SUBMITTED,
    )
    service, _, _ = build_service(tmp_path, request_contexts={request_id: context})
    client, token, _ = build_client(service, user_id=uuid4(), tmp_path=tmp_path)

    response = client.get(
        f"/api/v1/requests/{request_id}/attachments",
        headers=auth_header(token),
    )

    assert response.status_code == 404
    assert_standard_response_shape(response.json())
    assert response.json()["message"] == "Solicitud no encontrada"


def test_requests_manage_can_list_and_download_request_attachments(
    tmp_path: Path,
) -> None:
    request_id = uuid4()
    owner_id = uuid4()
    context = RequestAttachmentContext(
        request_id=request_id,
        requester_id=owner_id,
        status=RequestStatus.SUBMITTED,
    )
    service, _, _ = build_service(tmp_path, request_contexts={request_id: context})
    owner_client, owner_token, _ = build_client(
        service,
        user_id=owner_id,
        tmp_path=tmp_path,
    )
    create_response = owner_client.post(
        f"/api/v1/requests/{request_id}/attachments",
        headers=auth_header(owner_token),
        files=pdf_upload(content=b"%PDF-1.4 revision"),
    )
    attachment_id = create_response.json()["data"]["id"]
    admin_client, admin_token, _ = build_client(
        service,
        permissions=[PermissionCode.REQUESTS_MANAGE.value],
        tmp_path=tmp_path,
    )

    list_response = admin_client.get(
        f"/api/v1/requests/{request_id}/attachments",
        headers=auth_header(admin_token),
    )
    download_response = admin_client.get(
        f"/api/v1/requests/{request_id}/attachments/{attachment_id}/download",
        headers=auth_header(admin_token),
    )

    assert list_response.status_code == 200
    assert_standard_response_shape(list_response.json())
    assert len(list_response.json()["data"]) == 1
    assert download_response.status_code == 200
    assert download_response.content == b"%PDF-1.4 revision"


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/requests/{request_id}/attachments",
        "/api/v1/requests/{request_id}/attachments/{attachment_id}/download",
    ],
)
def test_request_attachment_reads_require_session(
    tmp_path: Path,
    path: str,
) -> None:
    request_id = uuid4()
    context = RequestAttachmentContext(
        request_id=request_id,
        requester_id=uuid4(),
        status=RequestStatus.SUBMITTED,
    )
    service, _, _ = build_service(tmp_path, request_contexts={request_id: context})
    client, _, _ = build_client(service, tmp_path=tmp_path)

    response = client.get(
        path.format(request_id=request_id, attachment_id=uuid4()),
    )

    assert response.status_code == 401
    assert_standard_response_shape(response.json())


def test_request_attachment_upload_requires_session(tmp_path: Path) -> None:
    request_id = uuid4()
    context = RequestAttachmentContext(
        request_id=request_id,
        requester_id=uuid4(),
        status=RequestStatus.SUBMITTED,
    )
    service, _, _ = build_service(tmp_path, request_contexts={request_id: context})
    client, _, _ = build_client(service, tmp_path=tmp_path)

    response = client.post(
        f"/api/v1/requests/{request_id}/attachments",
        files=pdf_upload(),
    )

    assert response.status_code == 401
    assert_standard_response_shape(response.json())
