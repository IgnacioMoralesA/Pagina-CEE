from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.audit.service import AuditService
from app.backend.auth.permissions import PermissionCode
from app.backend.auth.schemas import UserPrincipal
from app.backend.core.errors import AppError
from app.backend.core.responses import ErrorDetail
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


class ContentRepository(Protocol):
    async def category_exists(self, category_id: UUID) -> bool:
        ...

    async def list_news(
        self,
        *,
        status: PublicationStatus,
        category_id: UUID | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[NewsResponse]:
        ...

    async def get_news(self, news_id: UUID) -> NewsResponse | None:
        ...

    async def create_news(
        self,
        *,
        actor_id: UUID,
        slug: str,
        payload: NewsCreateRequest,
    ) -> NewsResponse:
        ...

    async def update_news(
        self,
        *,
        news_id: UUID,
        fields: dict[str, Any],
    ) -> NewsResponse | None:
        ...

    async def archive_news(self, news_id: UUID) -> NewsResponse | None:
        ...

    async def publish_news(self, news_id: UUID) -> NewsResponse | None:
        ...

    async def list_announcements(
        self,
        *,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[AnnouncementResponse]:
        ...

    async def get_announcement(
        self,
        announcement_id: UUID,
    ) -> AnnouncementResponse | None:
        ...

    async def create_announcement(
        self,
        *,
        actor_id: UUID,
        slug: str,
        payload: AnnouncementCreateRequest,
    ) -> AnnouncementResponse:
        ...

    async def update_announcement(
        self,
        *,
        announcement_id: UUID,
        fields: dict[str, Any],
    ) -> AnnouncementResponse | None:
        ...

    async def publish_announcement(
        self,
        announcement_id: UUID,
    ) -> AnnouncementResponse | None:
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


class DatabaseContentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def category_exists(self, category_id: UUID) -> bool:
        result = await self.db.execute(
            text(
                """
                SELECT 1
                FROM publication_categories
                WHERE id = :category_id
                  AND is_active IS TRUE
                  AND deleted_at IS NULL
                """
            ),
            {"category_id": category_id},
        )
        return result.scalar_one_or_none() is not None

    async def list_news(
        self,
        *,
        status: PublicationStatus,
        category_id: UUID | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[NewsResponse]:
        where_sql, params = _publication_where(
            table_alias="n",
            status=status,
            category_id=category_id,
        )
        count_result = await self.db.execute(
            text(f"SELECT count(*) FROM news n WHERE {where_sql}"),
            params,
        )
        result = await self.db.execute(
            text(
                f"""
                {_NEWS_SELECT}
                WHERE {where_sql}
                ORDER BY n.published_at DESC NULLS LAST, n.created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {**params, "limit": limit, "offset": offset},
        )
        return PaginatedResponse[NewsResponse](
            items=[_news_from_row(row) for row in result.mappings()],
            total=int(count_result.scalar_one()),
            limit=limit,
            offset=offset,
        )

    async def get_news(self, news_id: UUID) -> NewsResponse | None:
        result = await self.db.execute(
            text(
                f"""
                {_NEWS_SELECT}
                WHERE n.id = :news_id
                  AND n.deleted_at IS NULL
                """
            ),
            {"news_id": news_id},
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _news_from_row(row)

    async def create_news(
        self,
        *,
        actor_id: UUID,
        slug: str,
        payload: NewsCreateRequest,
    ) -> NewsResponse:
        result = await self.db.execute(
            text(
                """
                INSERT INTO news (
                    title,
                    slug,
                    summary,
                    content,
                    author_id,
                    category_id,
                    status,
                    image_url
                )
                VALUES (
                    :title,
                    :slug,
                    :summary,
                    :content,
                    :author_id,
                    :category_id,
                    CAST(:status AS publication_status),
                    :image_url
                )
                RETURNING id
                """
            ),
            {
                "title": payload.title,
                "slug": slug,
                "summary": payload.summary,
                "content": payload.content,
                "author_id": actor_id,
                "category_id": payload.category_id,
                "status": PublicationStatus.DRAFT.value,
                "image_url": payload.image_url,
            },
        )
        news_id = UUID(str(result.scalar_one()))
        created = await self.get_news(news_id)
        if created is None:  # pragma: no cover - defensive guard.
            raise AppError(status_code=500, message="Error interno del servidor")
        return created

    async def update_news(
        self,
        *,
        news_id: UUID,
        fields: dict[str, Any],
    ) -> NewsResponse | None:
        result = await self._update_publication(
            table_name="news",
            entity_id=news_id,
            fields=fields,
        )
        if result is None:
            return None
        return await self.get_news(news_id)

    async def archive_news(self, news_id: UUID) -> NewsResponse | None:
        result = await self.db.execute(
            text(
                """
                UPDATE news
                SET status = CAST(:status AS publication_status),
                    updated_at = now()
                WHERE id = :news_id
                  AND deleted_at IS NULL
                RETURNING id
                """
            ),
            {"news_id": news_id, "status": PublicationStatus.ARCHIVED.value},
        )
        if result.scalar_one_or_none() is None:
            return None
        return await self.get_news(news_id)

    async def publish_news(self, news_id: UUID) -> NewsResponse | None:
        result = await self.db.execute(
            text(
                """
                UPDATE news
                SET status = CAST(:status AS publication_status),
                    published_at = now(),
                    updated_at = now()
                WHERE id = :news_id
                  AND deleted_at IS NULL
                RETURNING id
                """
            ),
            {"news_id": news_id, "status": PublicationStatus.PUBLISHED.value},
        )
        if result.scalar_one_or_none() is None:
            return None
        return await self.get_news(news_id)

    async def list_announcements(
        self,
        *,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[AnnouncementResponse]:
        params: dict[str, Any] = {"status": PublicationStatus.PUBLISHED.value}
        count_result = await self.db.execute(
            text(
                """
                SELECT count(*)
                FROM announcements a
                WHERE a.deleted_at IS NULL
                  AND a.status = CAST(:status AS publication_status)
                """
            ),
            params,
        )
        result = await self.db.execute(
            text(
                f"""
                {_ANNOUNCEMENT_SELECT}
                WHERE a.deleted_at IS NULL
                  AND a.status = CAST(:status AS publication_status)
                ORDER BY a.priority ASC,
                         a.published_at DESC NULLS LAST,
                         a.created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {**params, "limit": limit, "offset": offset},
        )
        return PaginatedResponse[AnnouncementResponse](
            items=[_announcement_from_row(row) for row in result.mappings()],
            total=int(count_result.scalar_one()),
            limit=limit,
            offset=offset,
        )

    async def get_announcement(
        self,
        announcement_id: UUID,
    ) -> AnnouncementResponse | None:
        result = await self.db.execute(
            text(
                f"""
                {_ANNOUNCEMENT_SELECT}
                WHERE a.id = :announcement_id
                  AND a.deleted_at IS NULL
                """
            ),
            {"announcement_id": announcement_id},
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _announcement_from_row(row)

    async def create_announcement(
        self,
        *,
        actor_id: UUID,
        slug: str,
        payload: AnnouncementCreateRequest,
    ) -> AnnouncementResponse:
        result = await self.db.execute(
            text(
                """
                INSERT INTO announcements (
                    title,
                    slug,
                    summary,
                    content,
                    author_id,
                    category_id,
                    status,
                    priority,
                    expires_at
                )
                VALUES (
                    :title,
                    :slug,
                    :summary,
                    :content,
                    :author_id,
                    :category_id,
                    CAST(:status AS publication_status),
                    :priority,
                    :expires_at
                )
                RETURNING id
                """
            ),
            {
                "title": payload.title,
                "slug": slug,
                "summary": payload.summary,
                "content": payload.content,
                "author_id": actor_id,
                "category_id": payload.category_id,
                "status": PublicationStatus.DRAFT.value,
                "priority": payload.priority,
                "expires_at": payload.expires_at,
            },
        )
        announcement_id = UUID(str(result.scalar_one()))
        created = await self.get_announcement(announcement_id)
        if created is None:  # pragma: no cover - defensive guard.
            raise AppError(status_code=500, message="Error interno del servidor")
        return created

    async def update_announcement(
        self,
        *,
        announcement_id: UUID,
        fields: dict[str, Any],
    ) -> AnnouncementResponse | None:
        result = await self._update_publication(
            table_name="announcements",
            entity_id=announcement_id,
            fields=fields,
        )
        if result is None:
            return None
        return await self.get_announcement(announcement_id)

    async def publish_announcement(
        self,
        announcement_id: UUID,
    ) -> AnnouncementResponse | None:
        result = await self.db.execute(
            text(
                """
                UPDATE announcements
                SET status = CAST(:status AS publication_status),
                    published_at = now(),
                    updated_at = now()
                WHERE id = :announcement_id
                  AND deleted_at IS NULL
                RETURNING id
                """
            ),
            {
                "announcement_id": announcement_id,
                "status": PublicationStatus.PUBLISHED.value,
            },
        )
        if result.scalar_one_or_none() is None:
            return None
        return await self.get_announcement(announcement_id)

    async def commit(self) -> None:
        await self.db.commit()

    async def rollback(self) -> None:
        await self.db.rollback()

    async def _update_publication(
        self,
        *,
        table_name: str,
        entity_id: UUID,
        fields: dict[str, Any],
    ) -> UUID | None:
        allowed_fields = {
            "title",
            "summary",
            "content",
            "category_id",
            "image_url",
            "priority",
            "expires_at",
        }
        assignments = []
        params: dict[str, Any] = {"entity_id": entity_id}
        for field, value in fields.items():
            if field not in allowed_fields:
                continue
            assignments.append(f"{field} = :{field}")
            params[field] = value

        if not assignments:
            return entity_id

        assignments.append("updated_at = now()")
        result = await self.db.execute(
            text(
                f"""
                UPDATE {table_name}
                SET {", ".join(assignments)}
                WHERE id = :entity_id
                  AND deleted_at IS NULL
                RETURNING id
                """
            ),
            params,
        )
        updated_id = result.scalar_one_or_none()
        if updated_id is None:
            return None
        return UUID(str(updated_id))


class ContentService:
    def __init__(
        self,
        repository: ContentRepository,
        auditor: AdministrativeAuditor | None = None,
    ) -> None:
        self.repository = repository
        self.auditor = auditor

    async def list_news(
        self,
        *,
        current_user: UserPrincipal | None,
        status: PublicationStatus | None,
        category_id: UUID | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[NewsResponse]:
        if status is not None and status != PublicationStatus.PUBLISHED:
            _ensure_content_permission(current_user)
        effective_status = status or PublicationStatus.PUBLISHED
        return await self.repository.list_news(
            status=effective_status,
            category_id=category_id,
            limit=limit,
            offset=offset,
        )

    async def get_news(
        self,
        *,
        news_id: UUID,
        current_user: UserPrincipal | None,
    ) -> NewsResponse:
        news = await self.repository.get_news(news_id)
        if news is None:
            raise AppError(status_code=404, message="Noticia no encontrada")

        if news.status == PublicationStatus.PUBLISHED:
            return news

        if current_user is None:
            raise AppError(status_code=404, message="Noticia no encontrada")
        _ensure_content_permission(current_user)
        return news

    async def create_news(
        self,
        *,
        actor: UserPrincipal,
        payload: NewsCreateRequest,
    ) -> NewsResponse:
        await self._ensure_category_exists(payload.category_id)
        slug = _build_slug(payload.title)
        try:
            created = await self.repository.create_news(
                actor_id=actor.id,
                slug=slug,
                payload=payload,
            )
            await self._record_admin_action(
                actor_id=actor.id,
                entity_type="news",
                entity_id=created.id,
                metadata={
                    "action": "news.created",
                    "status": created.status.value,
                },
            )
            await self.repository.commit()
            return created
        except Exception:
            await self.repository.rollback()
            raise

    async def update_news(
        self,
        *,
        actor: UserPrincipal,
        news_id: UUID,
        payload: NewsUpdateRequest,
    ) -> NewsResponse:
        existing = await self.repository.get_news(news_id)
        if existing is None:
            raise AppError(status_code=404, message="Noticia no encontrada")
        _ensure_not_archived(existing.status, "Noticia archivada no modificable")

        fields = payload.model_dump(exclude_unset=True)
        _ensure_update_fields(fields)
        await self._ensure_category_exists(fields.get("category_id"))

        try:
            updated = await self.repository.update_news(
                news_id=news_id,
                fields=fields,
            )
            if updated is None:
                raise AppError(status_code=404, message="Noticia no encontrada")
            await self._record_admin_action(
                actor_id=actor.id,
                entity_type="news",
                entity_id=news_id,
                metadata={
                    "action": "news.updated",
                    "changed_fields": sorted(fields),
                },
            )
            await self.repository.commit()
            return updated
        except Exception:
            await self.repository.rollback()
            raise

    async def archive_news(
        self,
        *,
        actor: UserPrincipal,
        news_id: UUID,
    ) -> NewsResponse:
        existing = await self.repository.get_news(news_id)
        if existing is None:
            raise AppError(status_code=404, message="Noticia no encontrada")

        if existing.status == PublicationStatus.ARCHIVED:
            return existing

        try:
            archived = await self.repository.archive_news(news_id)
            if archived is None:
                raise AppError(status_code=404, message="Noticia no encontrada")
            await self._record_admin_action(
                actor_id=actor.id,
                entity_type="news",
                entity_id=news_id,
                metadata={
                    "action": "news.archived",
                    "old_status": existing.status.value,
                    "new_status": archived.status.value,
                },
            )
            await self.repository.commit()
            return archived
        except Exception:
            await self.repository.rollback()
            raise

    async def publish_news(
        self,
        *,
        actor: UserPrincipal,
        news_id: UUID,
    ) -> NewsResponse:
        existing = await self.repository.get_news(news_id)
        if existing is None:
            raise AppError(status_code=404, message="Noticia no encontrada")
        _ensure_not_archived(existing.status, "Noticia archivada no modificable")
        _ensure_publishable(existing.title, existing.content)

        if existing.status == PublicationStatus.PUBLISHED:
            return existing

        try:
            published = await self.repository.publish_news(news_id)
            if published is None:
                raise AppError(status_code=404, message="Noticia no encontrada")
            await self._record_admin_action(
                actor_id=actor.id,
                entity_type="news",
                entity_id=news_id,
                metadata={
                    "action": "news.published",
                    "old_status": existing.status.value,
                    "new_status": published.status.value,
                },
            )
            await self.repository.commit()
            return published
        except Exception:
            await self.repository.rollback()
            raise

    async def list_announcements(
        self,
        *,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[AnnouncementResponse]:
        return await self.repository.list_announcements(limit=limit, offset=offset)

    async def create_announcement(
        self,
        *,
        actor: UserPrincipal,
        payload: AnnouncementCreateRequest,
    ) -> AnnouncementResponse:
        await self._ensure_category_exists(payload.category_id)
        slug = _build_slug(payload.title)
        try:
            created = await self.repository.create_announcement(
                actor_id=actor.id,
                slug=slug,
                payload=payload,
            )
            await self._record_admin_action(
                actor_id=actor.id,
                entity_type="announcements",
                entity_id=created.id,
                metadata={
                    "action": "announcement.created",
                    "status": created.status.value,
                },
            )
            await self.repository.commit()
            return created
        except Exception:
            await self.repository.rollback()
            raise

    async def update_announcement(
        self,
        *,
        actor: UserPrincipal,
        announcement_id: UUID,
        payload: AnnouncementUpdateRequest,
    ) -> AnnouncementResponse:
        existing = await self.repository.get_announcement(announcement_id)
        if existing is None:
            raise AppError(status_code=404, message="Comunicado no encontrado")
        _ensure_not_archived(existing.status, "Comunicado archivado no modificable")

        fields = payload.model_dump(exclude_unset=True)
        _ensure_update_fields(fields)
        await self._ensure_category_exists(fields.get("category_id"))

        try:
            updated = await self.repository.update_announcement(
                announcement_id=announcement_id,
                fields=fields,
            )
            if updated is None:
                raise AppError(status_code=404, message="Comunicado no encontrado")
            await self._record_admin_action(
                actor_id=actor.id,
                entity_type="announcements",
                entity_id=announcement_id,
                metadata={
                    "action": "announcement.updated",
                    "changed_fields": sorted(fields),
                },
            )
            await self.repository.commit()
            return updated
        except Exception:
            await self.repository.rollback()
            raise

    async def publish_announcement(
        self,
        *,
        actor: UserPrincipal,
        announcement_id: UUID,
    ) -> AnnouncementResponse:
        existing = await self.repository.get_announcement(announcement_id)
        if existing is None:
            raise AppError(status_code=404, message="Comunicado no encontrado")
        _ensure_not_archived(existing.status, "Comunicado archivado no modificable")
        _ensure_publishable(existing.title, existing.content)
        _ensure_announcement_expiration(existing.expires_at)

        if existing.status == PublicationStatus.PUBLISHED:
            return existing

        try:
            published = await self.repository.publish_announcement(announcement_id)
            if published is None:
                raise AppError(status_code=404, message="Comunicado no encontrado")
            await self._record_admin_action(
                actor_id=actor.id,
                entity_type="announcements",
                entity_id=announcement_id,
                metadata={
                    "action": "announcement.published",
                    "old_status": existing.status.value,
                    "new_status": published.status.value,
                },
            )
            await self.repository.commit()
            return published
        except Exception:
            await self.repository.rollback()
            raise

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


def create_content_service(db: AsyncSession) -> ContentService:
    return ContentService(DatabaseContentRepository(db), AuditService(db))


def _publication_where(
    *,
    table_alias: str,
    status: PublicationStatus,
    category_id: UUID | None,
) -> tuple[str, dict[str, Any]]:
    params: dict[str, Any] = {"status": status.value}
    conditions = [
        f"{table_alias}.deleted_at IS NULL",
        f"{table_alias}.status = CAST(:status AS publication_status)",
    ]
    if category_id is not None:
        conditions.append(f"{table_alias}.category_id = :category_id")
        params["category_id"] = category_id
    return " AND ".join(conditions), params


def _ensure_content_permission(current_user: UserPrincipal | None) -> None:
    if current_user is None:
        raise AppError(status_code=401, message="No autenticado")
    if PermissionCode.CONTENT_PUBLISH.value in set(current_user.permissions):
        return
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


def _ensure_not_archived(status: PublicationStatus, message: str) -> None:
    if status != PublicationStatus.ARCHIVED:
        return
    raise AppError(
        status_code=409,
        message=message,
    )


def _ensure_publishable(title: str, content: str) -> None:
    if title.strip() and content.strip():
        return
    raise AppError(
        status_code=422,
        message="No se puede publicar contenido vacio",
    )


def _ensure_announcement_expiration(expires_at: datetime | None) -> None:
    if expires_at is None:
        return
    if expires_at > datetime.now(timezone.utc):
        return
    raise AppError(
        status_code=422,
        message="Fecha de expiracion invalida",
        errors=[
            ErrorDetail(
                field="expires_at",
                detail="La fecha de expiracion debe ser futura",
            )
        ],
    )


def _ensure_update_fields(fields: dict[str, Any]) -> None:
    if fields:
        return
    raise AppError(
        status_code=422,
        message="No hay campos para actualizar",
    )


def _build_slug(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_title).strip("-").lower()
    return f"{slug or 'publicacion'}-{uuid4().hex[:8]}"


def _normalize_status(value: object) -> PublicationStatus:
    return PublicationStatus(str(value).split(".")[-1].upper())


def _news_from_row(row: Any) -> NewsResponse:
    return NewsResponse(
        id=UUID(str(row["id"])),
        title=str(row["title"]),
        slug=str(row["slug"]),
        summary=row["summary"],
        content=str(row["content"]),
        author_id=UUID(str(row["author_id"])),
        author_name=row["author_name"],
        category_id=UUID(str(row["category_id"])) if row["category_id"] else None,
        category_name=row["category_name"],
        category_slug=row["category_slug"],
        status=_normalize_status(row["status"]),
        published_at=row["published_at"],
        image_url=row["image_url"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _announcement_from_row(row: Any) -> AnnouncementResponse:
    return AnnouncementResponse(
        id=UUID(str(row["id"])),
        title=str(row["title"]),
        slug=str(row["slug"]),
        summary=row["summary"],
        content=str(row["content"]),
        author_id=UUID(str(row["author_id"])),
        author_name=row["author_name"],
        category_id=UUID(str(row["category_id"])) if row["category_id"] else None,
        category_name=row["category_name"],
        category_slug=row["category_slug"],
        status=_normalize_status(row["status"]),
        priority=int(row["priority"]),
        published_at=row["published_at"],
        expires_at=row["expires_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


_NEWS_SELECT = """
SELECT
    n.id,
    n.title,
    n.slug,
    n.summary,
    n.content,
    n.author_id,
    u.name AS author_name,
    n.category_id,
    c.name AS category_name,
    c.slug AS category_slug,
    n.status,
    n.published_at,
    n.image_url,
    n.created_at,
    n.updated_at
FROM news n
JOIN users u ON u.id = n.author_id
LEFT JOIN publication_categories c ON c.id = n.category_id
"""


_ANNOUNCEMENT_SELECT = """
SELECT
    a.id,
    a.title,
    a.slug,
    a.summary,
    a.content,
    a.author_id,
    u.name AS author_name,
    a.category_id,
    c.name AS category_name,
    c.slug AS category_slug,
    a.status,
    a.priority,
    a.published_at,
    a.expires_at,
    a.created_at,
    a.updated_at
FROM announcements a
JOIN users u ON u.id = a.author_id
LEFT JOIN publication_categories c ON c.id = a.category_id
"""
