from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.backend.auth.dependencies import get_auth_context_validator
from app.backend.auth.jwt import create_access_token
from app.backend.auth.permissions import PermissionCode, RoleCode
from app.backend.auth.schemas import TokenClaims, UserPrincipal
from app.backend.content.dependencies import get_content_service
from app.backend.content.schemas import (
    AnnouncementCreateRequest,
    AnnouncementResponse,
    AnnouncementUpdateRequest,
    NewsCreateRequest,
    NewsResponse,
    NewsUpdateRequest,
    PaginatedResponse,
    PublicationStatus,
)
from app.backend.content.service import ContentService
from app.backend.core.config import Settings
from app.backend.core.errors import AppError
from app.backend.main import create_app


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


class FakeContentRepository:
    def __init__(
        self,
        *,
        news: list[NewsResponse] | None = None,
        announcements: list[AnnouncementResponse] | None = None,
        category_exists: bool = True,
    ) -> None:
        self.news = {item.id: item for item in news or []}
        self.announcements = {item.id: item for item in announcements or []}
        self.category_exists_value = category_exists
        self.committed = False
        self.rolled_back = False

    async def category_exists(self, category_id: UUID) -> bool:
        return self.category_exists_value

    async def list_news(
        self,
        *,
        status: PublicationStatus,
        category_id: UUID | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[NewsResponse]:
        items = [
            item
            for item in self.news.values()
            if item.status == status
            and (category_id is None or item.category_id == category_id)
        ]
        return PaginatedResponse[NewsResponse](
            items=items[offset : offset + limit],
            total=len(items),
            limit=limit,
            offset=offset,
        )

    async def get_news(self, news_id: UUID) -> NewsResponse | None:
        return self.news.get(news_id)

    async def create_news(
        self,
        *,
        actor_id: UUID,
        slug: str,
        payload: NewsCreateRequest,
    ) -> NewsResponse:
        item = build_news_response(
            uuid4(),
            payload.title,
            status=PublicationStatus.DRAFT,
            author_id=actor_id,
            slug=slug,
            content=payload.content,
            summary=payload.summary,
            category_id=payload.category_id,
            image_url=payload.image_url,
        )
        self.news[item.id] = item
        return item

    async def update_news(
        self,
        *,
        news_id: UUID,
        fields: dict[str, object],
    ) -> NewsResponse | None:
        item = self.news.get(news_id)
        if item is None:
            return None
        updated = item.model_copy(update=fields)
        self.news[news_id] = updated
        return updated

    async def archive_news(self, news_id: UUID) -> NewsResponse | None:
        item = self.news.get(news_id)
        if item is None:
            return None
        updated = item.model_copy(update={"status": PublicationStatus.ARCHIVED})
        self.news[news_id] = updated
        return updated

    async def publish_news(self, news_id: UUID) -> NewsResponse | None:
        item = self.news.get(news_id)
        if item is None:
            return None
        updated = item.model_copy(
            update={
                "status": PublicationStatus.PUBLISHED,
                "published_at": datetime.now(timezone.utc),
            }
        )
        self.news[news_id] = updated
        return updated

    async def list_announcements(
        self,
        *,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[AnnouncementResponse]:
        items = [
            item
            for item in self.announcements.values()
            if item.status == PublicationStatus.PUBLISHED
        ]
        return PaginatedResponse[AnnouncementResponse](
            items=items[offset : offset + limit],
            total=len(items),
            limit=limit,
            offset=offset,
        )

    async def get_announcement(
        self,
        announcement_id: UUID,
    ) -> AnnouncementResponse | None:
        return self.announcements.get(announcement_id)

    async def create_announcement(
        self,
        *,
        actor_id: UUID,
        slug: str,
        payload: AnnouncementCreateRequest,
    ) -> AnnouncementResponse:
        item = build_announcement_response(
            uuid4(),
            payload.title,
            status=PublicationStatus.DRAFT,
            author_id=actor_id,
            slug=slug,
            content=payload.content,
            summary=payload.summary,
            category_id=payload.category_id,
            priority=payload.priority,
            expires_at=payload.expires_at,
        )
        self.announcements[item.id] = item
        return item

    async def update_announcement(
        self,
        *,
        announcement_id: UUID,
        fields: dict[str, object],
    ) -> AnnouncementResponse | None:
        item = self.announcements.get(announcement_id)
        if item is None:
            return None
        updated = item.model_copy(update=fields)
        self.announcements[announcement_id] = updated
        return updated

    async def publish_announcement(
        self,
        announcement_id: UUID,
    ) -> AnnouncementResponse | None:
        item = self.announcements.get(announcement_id)
        if item is None:
            return None
        updated = item.model_copy(
            update={
                "status": PublicationStatus.PUBLISHED,
                "published_at": datetime.now(timezone.utc),
            }
        )
        self.announcements[announcement_id] = updated
        return updated

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def build_news_response(
    news_id: UUID,
    title: str,
    *,
    status: PublicationStatus,
    author_id: UUID | None = None,
    slug: str = "noticia-demo",
    content: str = "Contenido de la noticia",
    summary: str | None = "Resumen",
    category_id: UUID | None = None,
    image_url: str | None = None,
) -> NewsResponse:
    now = datetime.now(timezone.utc)
    return NewsResponse(
        id=news_id,
        title=title,
        slug=slug,
        summary=summary,
        content=content,
        author_id=author_id or uuid4(),
        author_name="Admin Demo",
        category_id=category_id,
        category_name=None,
        category_slug=None,
        status=status,
        published_at=now if status == PublicationStatus.PUBLISHED else None,
        image_url=image_url,
        created_at=now,
        updated_at=now,
    )


def build_announcement_response(
    announcement_id: UUID,
    title: str,
    *,
    status: PublicationStatus,
    author_id: UUID | None = None,
    slug: str = "comunicado-demo",
    content: str = "Contenido del comunicado",
    summary: str | None = "Resumen",
    category_id: UUID | None = None,
    priority: int = 3,
    expires_at: datetime | None = None,
) -> AnnouncementResponse:
    now = datetime.now(timezone.utc)
    return AnnouncementResponse(
        id=announcement_id,
        title=title,
        slug=slug,
        summary=summary,
        content=content,
        author_id=author_id or uuid4(),
        author_name="Admin Demo",
        category_id=category_id,
        category_name=None,
        category_slug=None,
        status=status,
        priority=priority,
        published_at=now if status == PublicationStatus.PUBLISHED else None,
        expires_at=expires_at,
        created_at=now,
        updated_at=now,
    )


def build_actor(
    *,
    permissions: list[str] | None = None,
) -> UserPrincipal:
    return UserPrincipal(
        id=uuid4(),
        session_id=uuid4(),
        email="admin@example.edu",
        name="Admin Demo",
        role=RoleCode.ADMIN,
        roles=[RoleCode.ADMIN],
        permissions=permissions or [PermissionCode.CONTENT_PUBLISH.value],
    )


def build_client(
    service: ContentService,
    *,
    permissions: list[str] | None = None,
) -> tuple[TestClient, str]:
    settings = Settings(jwt_secret_key="unit-test-secret")
    app = create_app(settings)
    app.dependency_overrides[get_content_service] = lambda: service
    app.dependency_overrides[get_auth_context_validator] = lambda: (
        StaticAuthContextValidator(
            roles=[RoleCode.ADMIN],
            permissions=permissions or [],
        )
    )
    token, _ = create_access_token(
        user_id=uuid4(),
        session_id=uuid4(),
        email="admin@example.edu",
        name="Admin Demo",
        roles=[RoleCode.ADMIN],
        permissions=[],
        settings=settings,
    )
    return TestClient(app), token


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def assert_standard_response_shape(payload: dict[str, object]) -> None:
    assert set(payload) == {"data", "message", "errors"}


def test_public_user_can_list_published_news() -> None:
    published = build_news_response(
        uuid4(),
        "Noticia publica",
        status=PublicationStatus.PUBLISHED,
    )
    draft = build_news_response(uuid4(), "Borrador", status=PublicationStatus.DRAFT)
    service = ContentService(FakeContentRepository(news=[published, draft]))
    client, _ = build_client(service)

    response = client.get("/api/v1/news")

    assert response.status_code == 200
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Noticias obtenidas"
    assert payload["data"]["total"] == 1
    assert payload["data"]["items"][0]["id"] == str(published.id)


def test_public_user_does_not_see_drafts() -> None:
    draft = build_news_response(uuid4(), "Borrador", status=PublicationStatus.DRAFT)
    service = ContentService(FakeContentRepository(news=[draft]))
    client, _ = build_client(service)

    list_response = client.get("/api/v1/news")
    detail_response = client.get(f"/api/v1/news/{draft.id}")

    assert list_response.status_code == 200
    assert list_response.json()["data"]["items"] == []
    assert detail_response.status_code == 404
    assert detail_response.json()["message"] == "Noticia no encontrada"


def test_public_user_does_not_see_archived_news_detail() -> None:
    archived = build_news_response(
        uuid4(),
        "Archivada",
        status=PublicationStatus.ARCHIVED,
    )
    service = ContentService(FakeContentRepository(news=[archived]))
    client, _ = build_client(service)

    response = client.get(f"/api/v1/news/{archived.id}")

    assert response.status_code == 404
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Noticia no encontrada"


def test_public_status_filter_for_drafts_requires_authentication() -> None:
    draft = build_news_response(uuid4(), "Borrador", status=PublicationStatus.DRAFT)
    service = ContentService(FakeContentRepository(news=[draft]))
    client, _ = build_client(service)

    response = client.get("/api/v1/news?status=DRAFT")

    assert response.status_code == 401
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "No autenticado"


def test_authenticated_user_without_permission_cannot_filter_draft_or_archived_news() -> None:
    draft = build_news_response(uuid4(), "Borrador", status=PublicationStatus.DRAFT)
    archived = build_news_response(
        uuid4(),
        "Archivada",
        status=PublicationStatus.ARCHIVED,
    )
    service = ContentService(FakeContentRepository(news=[draft, archived]))
    client, token = build_client(service, permissions=[])

    draft_response = client.get(
        "/api/v1/news?status=DRAFT",
        headers=auth_header(token),
    )
    archived_response = client.get(
        "/api/v1/news?status=ARCHIVED",
        headers=auth_header(token),
    )

    assert draft_response.status_code == 403
    assert archived_response.status_code == 403
    assert draft_response.json()["message"] == "Permisos insuficientes"
    assert archived_response.json()["message"] == "Permisos insuficientes"


def test_admin_can_filter_draft_news_with_current_permission() -> None:
    draft = build_news_response(uuid4(), "Borrador", status=PublicationStatus.DRAFT)
    service = ContentService(FakeContentRepository(news=[draft]))
    client, token = build_client(
        service,
        permissions=[PermissionCode.CONTENT_PUBLISH.value],
    )

    response = client.get(
        "/api/v1/news?status=DRAFT",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["total"] == 1
    assert payload["data"]["items"][0]["status"] == "DRAFT"


def test_mutating_content_routes_require_session() -> None:
    draft_news = build_news_response(uuid4(), "Borrador", status=PublicationStatus.DRAFT)
    draft_announcement = build_announcement_response(
        uuid4(),
        "Comunicado borrador",
        status=PublicationStatus.DRAFT,
    )
    service = ContentService(
        FakeContentRepository(
            news=[draft_news],
            announcements=[draft_announcement],
        )
    )
    client, _ = build_client(
        service,
        permissions=[PermissionCode.CONTENT_PUBLISH.value],
    )

    requests = [
        ("post", "/api/v1/news", {"title": "Nueva noticia", "content": "Contenido"}),
        (
            "patch",
            f"/api/v1/news/{draft_news.id}",
            {"summary": "Resumen actualizado"},
        ),
        ("delete", f"/api/v1/news/{draft_news.id}", None),
        ("post", f"/api/v1/news/{draft_news.id}/publish", None),
        (
            "post",
            "/api/v1/announcements",
            {"title": "Nuevo comunicado", "content": "Contenido"},
        ),
        (
            "patch",
            f"/api/v1/announcements/{draft_announcement.id}",
            {"summary": "Resumen actualizado"},
        ),
        ("post", f"/api/v1/announcements/{draft_announcement.id}/publish", None),
    ]

    for method, path, json_body in requests:
        response = client.request(method, path, json=json_body)
        payload = response.json()
        assert response.status_code == 401
        assert_standard_response_shape(payload)
        assert payload["message"] == "No autenticado"


def test_mutating_content_routes_require_content_publish_permission() -> None:
    draft_news = build_news_response(uuid4(), "Borrador", status=PublicationStatus.DRAFT)
    draft_announcement = build_announcement_response(
        uuid4(),
        "Comunicado borrador",
        status=PublicationStatus.DRAFT,
    )
    service = ContentService(
        FakeContentRepository(
            news=[draft_news],
            announcements=[draft_announcement],
        )
    )
    client, token = build_client(service, permissions=[])

    requests = [
        ("post", "/api/v1/news", {"title": "Nueva noticia", "content": "Contenido"}),
        (
            "patch",
            f"/api/v1/news/{draft_news.id}",
            {"summary": "Resumen actualizado"},
        ),
        ("delete", f"/api/v1/news/{draft_news.id}", None),
        ("post", f"/api/v1/news/{draft_news.id}/publish", None),
        (
            "post",
            "/api/v1/announcements",
            {"title": "Nuevo comunicado", "content": "Contenido"},
        ),
        (
            "patch",
            f"/api/v1/announcements/{draft_announcement.id}",
            {"summary": "Resumen actualizado"},
        ),
        ("post", f"/api/v1/announcements/{draft_announcement.id}/publish", None),
    ]

    for method, path, json_body in requests:
        response = client.request(method, path, headers=auth_header(token), json=json_body)
        payload = response.json()
        assert response.status_code == 403
        assert_standard_response_shape(payload)
        assert payload["message"] == "Permisos insuficientes"
        assert payload["errors"][0]["field"] == "permissions"


def test_user_without_session_cannot_create_news() -> None:
    service = ContentService(FakeContentRepository())
    client, _ = build_client(service)

    response = client.post(
        "/api/v1/news",
        json={"title": "Nueva noticia", "content": "Contenido"},
    )

    assert response.status_code == 401
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "No autenticado"


def test_user_without_permission_receives_403_when_creating_news() -> None:
    service = ContentService(FakeContentRepository())
    client, token = build_client(service, permissions=[])

    response = client.post(
        "/api/v1/news",
        headers=auth_header(token),
        json={"title": "Nueva noticia", "content": "Contenido"},
    )

    assert response.status_code == 403
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Permisos insuficientes"


def test_empty_content_is_rejected_for_news_and_announcements() -> None:
    service = ContentService(FakeContentRepository())
    client, token = build_client(
        service,
        permissions=[PermissionCode.CONTENT_PUBLISH.value],
    )

    news_response = client.post(
        "/api/v1/news",
        headers=auth_header(token),
        json={"title": "Nueva noticia", "content": "   "},
    )
    announcement_response = client.post(
        "/api/v1/announcements",
        headers=auth_header(token),
        json={"title": "Nuevo comunicado", "content": "   "},
    )

    assert news_response.status_code == 422
    assert announcement_response.status_code == 422
    assert_standard_response_shape(news_response.json())
    assert_standard_response_shape(announcement_response.json())
    assert news_response.json()["message"] == "Solicitud invalida"
    assert announcement_response.json()["message"] == "Solicitud invalida"


def test_user_with_permission_can_create_news() -> None:
    service = ContentService(FakeContentRepository())
    client, token = build_client(
        service,
        permissions=[PermissionCode.CONTENT_PUBLISH.value],
    )

    response = client.post(
        "/api/v1/news",
        headers=auth_header(token),
        json={"title": "Nueva noticia", "content": "Contenido"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Noticia creada"
    assert payload["data"]["status"] == "DRAFT"
    assert payload["data"]["author_id"]


def test_user_with_permission_can_update_archive_and_publish_news_via_routes() -> None:
    news_to_update = build_news_response(
        uuid4(),
        "Borrador editable",
        status=PublicationStatus.DRAFT,
    )
    news_to_archive = build_news_response(
        uuid4(),
        "Borrador archivable",
        status=PublicationStatus.DRAFT,
    )
    news_to_publish = build_news_response(
        uuid4(),
        "Borrador publicable",
        status=PublicationStatus.DRAFT,
    )
    repository = FakeContentRepository(
        news=[news_to_update, news_to_archive, news_to_publish]
    )
    auditor = RecordingAuditor()
    service = ContentService(repository, auditor)
    client, token = build_client(
        service,
        permissions=[PermissionCode.CONTENT_PUBLISH.value],
    )

    update_response = client.patch(
        f"/api/v1/news/{news_to_update.id}",
        headers=auth_header(token),
        json={"summary": "Resumen actualizado"},
    )
    archive_response = client.delete(
        f"/api/v1/news/{news_to_archive.id}",
        headers=auth_header(token),
    )
    publish_response = client.post(
        f"/api/v1/news/{news_to_publish.id}/publish",
        headers=auth_header(token),
    )

    assert update_response.status_code == 200
    assert archive_response.status_code == 200
    assert publish_response.status_code == 200
    assert_standard_response_shape(update_response.json())
    assert_standard_response_shape(archive_response.json())
    assert_standard_response_shape(publish_response.json())
    assert update_response.json()["message"] == "Noticia actualizada"
    assert archive_response.json()["message"] == "Noticia archivada"
    assert publish_response.json()["message"] == "Noticia publicada"
    assert update_response.json()["data"]["summary"] == "Resumen actualizado"
    assert archive_response.json()["data"]["status"] == "ARCHIVED"
    assert publish_response.json()["data"]["status"] == "PUBLISHED"
    assert publish_response.json()["data"]["published_at"] is not None
    assert news_to_archive.id in repository.news
    assert repository.news[news_to_archive.id].status == PublicationStatus.ARCHIVED
    assert [event["metadata"]["action"] for event in auditor.events] == [
        "news.updated",
        "news.archived",
        "news.published",
    ]


def test_create_news_generates_administrative_audit() -> None:
    asyncio.run(_run_create_news_audit_check())


async def _run_create_news_audit_check() -> None:
    repository = FakeContentRepository()
    auditor = RecordingAuditor()
    service = ContentService(repository, auditor)
    actor = build_actor()

    created = await service.create_news(
        actor=actor,
        payload=NewsCreateRequest(title="Nueva noticia", content="Contenido"),
    )

    assert repository.committed is True
    assert auditor.events == [
        {
            "actor_id": actor.id,
            "entity_type": "news",
            "entity_id": created.id,
            "metadata": {"action": "news.created", "status": "DRAFT"},
        }
    ]


def test_publish_news_changes_status_and_published_at_and_generates_audit() -> None:
    asyncio.run(_run_publish_news_check())


async def _run_publish_news_check() -> None:
    draft = build_news_response(uuid4(), "Borrador", status=PublicationStatus.DRAFT)
    repository = FakeContentRepository(news=[draft])
    auditor = RecordingAuditor()
    service = ContentService(repository, auditor)
    actor = build_actor()

    published = await service.publish_news(actor=actor, news_id=draft.id)

    assert published.status == PublicationStatus.PUBLISHED
    assert published.published_at is not None
    assert repository.committed is True
    assert auditor.events == [
        {
            "actor_id": actor.id,
            "entity_type": "news",
            "entity_id": draft.id,
            "metadata": {
                "action": "news.published",
                "old_status": "DRAFT",
                "new_status": "PUBLISHED",
            },
        }
    ]


def test_archived_news_is_not_in_public_listing() -> None:
    archived = build_news_response(
        uuid4(),
        "Archivada",
        status=PublicationStatus.ARCHIVED,
    )
    service = ContentService(FakeContentRepository(news=[archived]))
    client, _ = build_client(service)

    response = client.get("/api/v1/news")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["total"] == 0
    assert payload["data"]["items"] == []


def test_archived_news_cannot_be_edited() -> None:
    archived = build_news_response(
        uuid4(),
        "Archivada",
        status=PublicationStatus.ARCHIVED,
    )
    service = ContentService(FakeContentRepository(news=[archived]))

    with pytest.raises(AppError) as exc_info:
        asyncio.run(
            service.update_news(
                actor=build_actor(),
                news_id=archived.id,
                payload=NewsUpdateRequest(title="Nuevo titulo"),
            )
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.message == "Noticia archivada no modificable"


def test_publish_empty_news_and_announcement_content_is_rejected() -> None:
    empty_news = build_news_response(
        uuid4(),
        "Borrador sin contenido",
        status=PublicationStatus.DRAFT,
        content="   ",
    )
    empty_announcement = build_announcement_response(
        uuid4(),
        "Comunicado sin contenido",
        status=PublicationStatus.DRAFT,
        content="   ",
    )
    service = ContentService(
        FakeContentRepository(
            news=[empty_news],
            announcements=[empty_announcement],
        )
    )

    with pytest.raises(AppError) as news_exc:
        asyncio.run(service.publish_news(actor=build_actor(), news_id=empty_news.id))
    with pytest.raises(AppError) as announcement_exc:
        asyncio.run(
            service.publish_announcement(
                actor=build_actor(),
                announcement_id=empty_announcement.id,
            )
        )

    assert news_exc.value.status_code == 422
    assert announcement_exc.value.status_code == 422
    assert news_exc.value.message == "No se puede publicar contenido vacio"
    assert announcement_exc.value.message == "No se puede publicar contenido vacio"


def test_public_user_can_list_only_published_announcements() -> None:
    published = build_announcement_response(
        uuid4(),
        "Comunicado publico",
        status=PublicationStatus.PUBLISHED,
    )
    draft = build_announcement_response(
        uuid4(),
        "Comunicado borrador",
        status=PublicationStatus.DRAFT,
    )
    service = ContentService(
        FakeContentRepository(announcements=[published, draft])
    )
    client, _ = build_client(service)

    response = client.get("/api/v1/announcements")

    assert response.status_code == 200
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Comunicados obtenidos"
    assert payload["data"]["total"] == 1
    assert payload["data"]["items"][0]["id"] == str(published.id)


def test_user_without_session_cannot_create_announcement() -> None:
    service = ContentService(FakeContentRepository())
    client, _ = build_client(service)

    response = client.post(
        "/api/v1/announcements",
        json={"title": "Nuevo comunicado", "content": "Contenido"},
    )

    assert response.status_code == 401
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "No autenticado"


def test_user_without_permission_receives_403_when_creating_announcement() -> None:
    service = ContentService(FakeContentRepository())
    client, token = build_client(service, permissions=[])

    response = client.post(
        "/api/v1/announcements",
        headers=auth_header(token),
        json={"title": "Nuevo comunicado", "content": "Contenido"},
    )

    assert response.status_code == 403
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Permisos insuficientes"


def test_user_with_permission_can_create_update_and_publish_announcement_via_routes() -> None:
    repository = FakeContentRepository()
    auditor = RecordingAuditor()
    service = ContentService(repository, auditor)
    client, token = build_client(
        service,
        permissions=[PermissionCode.CONTENT_PUBLISH.value],
    )

    create_response = client.post(
        "/api/v1/announcements",
        headers=auth_header(token),
        json={"title": "Nuevo comunicado", "content": "Contenido"},
    )
    announcement_id = create_response.json()["data"]["id"]
    update_response = client.patch(
        f"/api/v1/announcements/{announcement_id}",
        headers=auth_header(token),
        json={"summary": "Resumen actualizado"},
    )
    publish_response = client.post(
        f"/api/v1/announcements/{announcement_id}/publish",
        headers=auth_header(token),
    )

    assert create_response.status_code == 201
    assert update_response.status_code == 200
    assert publish_response.status_code == 200
    assert_standard_response_shape(create_response.json())
    assert_standard_response_shape(update_response.json())
    assert_standard_response_shape(publish_response.json())
    assert create_response.json()["message"] == "Comunicado creado"
    assert update_response.json()["message"] == "Comunicado actualizado"
    assert publish_response.json()["message"] == "Comunicado publicado"
    assert create_response.json()["data"]["status"] == "DRAFT"
    assert update_response.json()["data"]["summary"] == "Resumen actualizado"
    assert publish_response.json()["data"]["status"] == "PUBLISHED"
    assert publish_response.json()["data"]["published_at"] is not None
    assert [event["metadata"]["action"] for event in auditor.events] == [
        "announcement.created",
        "announcement.updated",
        "announcement.published",
    ]


def test_announcement_create_update_and_publish_follow_admin_rules() -> None:
    asyncio.run(_run_announcement_admin_rules_check())


async def _run_announcement_admin_rules_check() -> None:
    repository = FakeContentRepository()
    auditor = RecordingAuditor()
    service = ContentService(repository, auditor)
    actor = build_actor()
    expires_at = datetime.now(timezone.utc) + timedelta(days=2)

    created = await service.create_announcement(
        actor=actor,
        payload=AnnouncementCreateRequest(
            title="Nuevo comunicado",
            content="Contenido",
            expires_at=expires_at,
        ),
    )
    updated = await service.update_announcement(
        actor=actor,
        announcement_id=created.id,
        payload=AnnouncementUpdateRequest(summary="Resumen actualizado"),
    )
    published = await service.publish_announcement(
        actor=actor,
        announcement_id=created.id,
    )

    assert created.status == PublicationStatus.DRAFT
    assert updated.summary == "Resumen actualizado"
    assert published.status == PublicationStatus.PUBLISHED
    assert published.published_at is not None
    assert repository.committed is True
    assert [event["metadata"]["action"] for event in auditor.events] == [
        "announcement.created",
        "announcement.updated",
        "announcement.published",
    ]
