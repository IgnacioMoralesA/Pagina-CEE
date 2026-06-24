from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.audit.service import AuditService
from app.backend.auth.permissions import PermissionCode
from app.backend.auth.schemas import UserPrincipal
from app.backend.core.errors import AppError
from app.backend.core.responses import ErrorDetail
from app.backend.events.schemas import (
    EventAttendanceRequest,
    EventAttendanceResponse,
    EventCancelRequest,
    EventCreateRequest,
    EventRegistrationResponse,
    EventResponse,
    EventStatus,
    EventUpdateRequest,
    PaginatedResponse,
    RegistrationStatus,
)


class EventRepository(Protocol):
    async def category_exists(self, category_id: UUID) -> bool:
        ...

    async def list_events(
        self,
        *,
        status: EventStatus | None,
        category_id: UUID | None,
        upcoming_only: bool,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[EventResponse]:
        ...

    async def get_event(self, event_id: UUID) -> EventResponse | None:
        ...

    async def create_event(
        self,
        *,
        actor_id: UUID,
        payload: EventCreateRequest,
    ) -> EventResponse:
        ...

    async def update_event(
        self,
        *,
        event_id: UUID,
        fields: dict[str, Any],
    ) -> EventResponse | None:
        ...

    async def set_event_status(
        self,
        *,
        event_id: UUID,
        status: EventStatus,
    ) -> EventResponse | None:
        ...

    async def get_registration(
        self,
        *,
        event_id: UUID,
        user_id: UUID,
    ) -> EventRegistrationResponse | None:
        ...

    async def count_registered(self, event_id: UUID) -> int:
        ...

    async def create_registration(
        self,
        *,
        event_id: UUID,
        user_id: UUID,
    ) -> EventRegistrationResponse:
        ...

    async def reactivate_registration(
        self,
        *,
        event_id: UUID,
        user_id: UUID,
    ) -> EventRegistrationResponse | None:
        ...

    async def cancel_registration(
        self,
        *,
        event_id: UUID,
        user_id: UUID,
    ) -> EventRegistrationResponse | None:
        ...

    async def get_attendance(
        self,
        *,
        event_id: UUID,
        user_id: UUID,
    ) -> EventAttendanceResponse | None:
        ...

    async def create_attendance(
        self,
        *,
        event_id: UUID,
        user_id: UUID,
        checked_by: UUID,
        notes: str | None,
    ) -> EventAttendanceResponse:
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


class DatabaseEventRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def category_exists(self, category_id: UUID) -> bool:
        result = await self.db.execute(
            text(
                """
                SELECT 1
                FROM event_categories
                WHERE id = :category_id
                  AND is_active IS TRUE
                  AND deleted_at IS NULL
                """
            ),
            {"category_id": category_id},
        )
        return result.scalar_one_or_none() is not None

    async def list_events(
        self,
        *,
        status: EventStatus | None,
        category_id: UUID | None,
        upcoming_only: bool,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[EventResponse]:
        where_sql, params = _event_where(
            status=status,
            category_id=category_id,
            upcoming_only=upcoming_only,
        )
        count_result = await self.db.execute(
            text(f"SELECT count(*) FROM events e WHERE {where_sql}"),
            params,
        )
        result = await self.db.execute(
            text(
                f"""
                {_EVENT_SELECT}
                WHERE {where_sql}
                ORDER BY e.starts_at ASC, e.created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {**params, "limit": limit, "offset": offset},
        )
        return PaginatedResponse[EventResponse](
            items=[_event_from_row(row) for row in result.mappings()],
            total=int(count_result.scalar_one()),
            limit=limit,
            offset=offset,
        )

    async def get_event(self, event_id: UUID) -> EventResponse | None:
        result = await self.db.execute(
            text(
                f"""
                {_EVENT_SELECT}
                WHERE e.id = :event_id
                  AND e.deleted_at IS NULL
                """
            ),
            {"event_id": event_id},
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _event_from_row(row)

    async def create_event(
        self,
        *,
        actor_id: UUID,
        payload: EventCreateRequest,
    ) -> EventResponse:
        result = await self.db.execute(
            text(
                """
                INSERT INTO events (
                    category_id,
                    name,
                    description,
                    starts_at,
                    ends_at,
                    location,
                    capacity,
                    responsible_id,
                    status,
                    image_url
                )
                VALUES (
                    :category_id,
                    :name,
                    :description,
                    :starts_at,
                    :ends_at,
                    :location,
                    :capacity,
                    :responsible_id,
                    CAST(:status AS event_status),
                    :image_url
                )
                RETURNING id
                """
            ),
            {
                "category_id": payload.category_id,
                "name": payload.name,
                "description": payload.description,
                "starts_at": payload.starts_at,
                "ends_at": payload.ends_at,
                "location": payload.location,
                "capacity": payload.capacity,
                "responsible_id": actor_id,
                "status": EventStatus.PLANNED.value,
                "image_url": payload.image_url,
            },
        )
        event_id = UUID(str(result.scalar_one()))
        created = await self.get_event(event_id)
        if created is None:  # pragma: no cover - defensive guard.
            raise AppError(status_code=500, message="Error interno del servidor")
        return created

    async def update_event(
        self,
        *,
        event_id: UUID,
        fields: dict[str, Any],
    ) -> EventResponse | None:
        allowed_fields = {
            "category_id",
            "name",
            "description",
            "starts_at",
            "ends_at",
            "location",
            "capacity",
            "image_url",
        }
        assignments = []
        params: dict[str, Any] = {"event_id": event_id}
        for field, value in fields.items():
            if field not in allowed_fields:
                continue
            assignments.append(f"{field} = :{field}")
            params[field] = value

        if not assignments:
            return await self.get_event(event_id)

        assignments.append("updated_at = now()")
        result = await self.db.execute(
            text(
                f"""
                UPDATE events
                SET {", ".join(assignments)}
                WHERE id = :event_id
                  AND deleted_at IS NULL
                RETURNING id
                """
            ),
            params,
        )
        if result.scalar_one_or_none() is None:
            return None
        return await self.get_event(event_id)

    async def set_event_status(
        self,
        *,
        event_id: UUID,
        status: EventStatus,
    ) -> EventResponse | None:
        result = await self.db.execute(
            text(
                """
                UPDATE events
                SET status = CAST(:status AS event_status),
                    published_at = CASE
                        WHEN :status = 'PUBLISHED' THEN now()
                        ELSE published_at
                    END,
                    updated_at = now()
                WHERE id = :event_id
                  AND deleted_at IS NULL
                RETURNING id
                """
            ),
            {"event_id": event_id, "status": status.value},
        )
        if result.scalar_one_or_none() is None:
            return None
        return await self.get_event(event_id)

    async def get_registration(
        self,
        *,
        event_id: UUID,
        user_id: UUID,
    ) -> EventRegistrationResponse | None:
        result = await self.db.execute(
            text(
                """
                SELECT
                    id,
                    event_id,
                    user_id,
                    status,
                    registered_at,
                    cancelled_at,
                    created_at,
                    updated_at
                FROM event_registrations
                WHERE event_id = :event_id
                  AND user_id = :user_id
                """
            ),
            {"event_id": event_id, "user_id": user_id},
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _registration_from_row(row)

    async def count_registered(self, event_id: UUID) -> int:
        result = await self.db.execute(
            text(
                """
                SELECT count(*)
                FROM event_registrations
                WHERE event_id = :event_id
                  AND status = 'REGISTERED'
                """
            ),
            {"event_id": event_id},
        )
        return int(result.scalar_one())

    async def create_registration(
        self,
        *,
        event_id: UUID,
        user_id: UUID,
    ) -> EventRegistrationResponse:
        result = await self.db.execute(
            text(
                """
                INSERT INTO event_registrations (event_id, user_id, status)
                VALUES (:event_id, :user_id, 'REGISTERED')
                RETURNING id
                """
            ),
            {"event_id": event_id, "user_id": user_id},
        )
        registration_id = UUID(str(result.scalar_one()))
        created = await self._get_registration_by_id(registration_id)
        if created is None:  # pragma: no cover - defensive guard.
            raise AppError(status_code=500, message="Error interno del servidor")
        return created

    async def reactivate_registration(
        self,
        *,
        event_id: UUID,
        user_id: UUID,
    ) -> EventRegistrationResponse | None:
        result = await self.db.execute(
            text(
                """
                UPDATE event_registrations
                SET status = 'REGISTERED',
                    registered_at = now(),
                    cancelled_at = NULL,
                    updated_at = now()
                WHERE event_id = :event_id
                  AND user_id = :user_id
                RETURNING id
                """
            ),
            {"event_id": event_id, "user_id": user_id},
        )
        registration_id = result.scalar_one_or_none()
        if registration_id is None:
            return None
        return await self._get_registration_by_id(UUID(str(registration_id)))

    async def cancel_registration(
        self,
        *,
        event_id: UUID,
        user_id: UUID,
    ) -> EventRegistrationResponse | None:
        result = await self.db.execute(
            text(
                """
                UPDATE event_registrations
                SET status = 'CANCELLED',
                    cancelled_at = now(),
                    updated_at = now()
                WHERE event_id = :event_id
                  AND user_id = :user_id
                  AND status = 'REGISTERED'
                RETURNING id
                """
            ),
            {"event_id": event_id, "user_id": user_id},
        )
        registration_id = result.scalar_one_or_none()
        if registration_id is None:
            return None
        return await self._get_registration_by_id(UUID(str(registration_id)))

    async def get_attendance(
        self,
        *,
        event_id: UUID,
        user_id: UUID,
    ) -> EventAttendanceResponse | None:
        result = await self.db.execute(
            text(
                """
                SELECT
                    id,
                    event_id,
                    user_id,
                    checked_in_at,
                    checked_by,
                    notes,
                    created_at
                FROM event_attendance
                WHERE event_id = :event_id
                  AND user_id = :user_id
                """
            ),
            {"event_id": event_id, "user_id": user_id},
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _attendance_from_row(row)

    async def create_attendance(
        self,
        *,
        event_id: UUID,
        user_id: UUID,
        checked_by: UUID,
        notes: str | None,
    ) -> EventAttendanceResponse:
        result = await self.db.execute(
            text(
                """
                INSERT INTO event_attendance (
                    event_id,
                    user_id,
                    checked_by,
                    notes
                )
                VALUES (
                    :event_id,
                    :user_id,
                    :checked_by,
                    :notes
                )
                RETURNING id
                """
            ),
            {
                "event_id": event_id,
                "user_id": user_id,
                "checked_by": checked_by,
                "notes": notes,
            },
        )
        attendance_id = UUID(str(result.scalar_one()))
        created = await self._get_attendance_by_id(attendance_id)
        if created is None:  # pragma: no cover - defensive guard.
            raise AppError(status_code=500, message="Error interno del servidor")
        return created

    async def commit(self) -> None:
        await self.db.commit()

    async def rollback(self) -> None:
        await self.db.rollback()

    async def _get_registration_by_id(
        self,
        registration_id: UUID,
    ) -> EventRegistrationResponse | None:
        result = await self.db.execute(
            text(
                """
                SELECT
                    id,
                    event_id,
                    user_id,
                    status,
                    registered_at,
                    cancelled_at,
                    created_at,
                    updated_at
                FROM event_registrations
                WHERE id = :registration_id
                """
            ),
            {"registration_id": registration_id},
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _registration_from_row(row)

    async def _get_attendance_by_id(
        self,
        attendance_id: UUID,
    ) -> EventAttendanceResponse | None:
        result = await self.db.execute(
            text(
                """
                SELECT
                    id,
                    event_id,
                    user_id,
                    checked_in_at,
                    checked_by,
                    notes,
                    created_at
                FROM event_attendance
                WHERE id = :attendance_id
                """
            ),
            {"attendance_id": attendance_id},
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _attendance_from_row(row)


class EventService:
    def __init__(
        self,
        repository: EventRepository,
        auditor: AdministrativeAuditor | None = None,
    ) -> None:
        self.repository = repository
        self.auditor = auditor

    async def list_events(
        self,
        *,
        current_user: UserPrincipal | None,
        status: EventStatus | None,
        category_id: UUID | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[EventResponse]:
        if status is not None and status != EventStatus.PUBLISHED:
            _ensure_events_manage_permission(current_user)
        return await self.repository.list_events(
            status=status or EventStatus.PUBLISHED,
            category_id=category_id,
            upcoming_only=status is None,
            limit=limit,
            offset=offset,
        )

    async def get_event(
        self,
        *,
        event_id: UUID,
        current_user: UserPrincipal | None,
    ) -> EventResponse:
        event = await self.repository.get_event(event_id)
        if event is None:
            raise AppError(status_code=404, message="Evento no encontrado")
        if event.status == EventStatus.PUBLISHED:
            return event
        if current_user is None:
            raise AppError(status_code=404, message="Evento no encontrado")
        _ensure_events_manage_permission(current_user)
        return event

    async def create_event(
        self,
        *,
        actor: UserPrincipal,
        payload: EventCreateRequest,
    ) -> EventResponse:
        await self._ensure_category_exists(payload.category_id)
        try:
            created = await self.repository.create_event(
                actor_id=actor.id,
                payload=payload,
            )
            await self._record_admin_action(
                actor_id=actor.id,
                entity_id=created.id,
                metadata={"action": "event.created", "status": created.status.value},
            )
            await self.repository.commit()
            return created
        except Exception:
            await self.repository.rollback()
            raise

    async def update_event(
        self,
        *,
        actor: UserPrincipal,
        event_id: UUID,
        payload: EventUpdateRequest,
    ) -> EventResponse:
        existing = await self.repository.get_event(event_id)
        if existing is None:
            raise AppError(status_code=404, message="Evento no encontrado")

        fields = payload.model_dump(exclude_unset=True)
        _ensure_update_fields(fields)
        await self._ensure_category_exists(fields.get("category_id"))
        starts_at = fields.get("starts_at", existing.starts_at)
        ends_at = fields.get("ends_at", existing.ends_at)
        _ensure_dates(starts_at, ends_at)

        try:
            updated = await self.repository.update_event(
                event_id=event_id,
                fields=fields,
            )
            if updated is None:
                raise AppError(status_code=404, message="Evento no encontrado")
            await self._record_admin_action(
                actor_id=actor.id,
                entity_id=event_id,
                metadata={
                    "action": "event.updated",
                    "changed_fields": sorted(fields),
                },
            )
            await self.repository.commit()
            return updated
        except Exception:
            await self.repository.rollback()
            raise

    async def publish_event(
        self,
        *,
        actor: UserPrincipal,
        event_id: UUID,
    ) -> EventResponse:
        existing = await self.repository.get_event(event_id)
        if existing is None:
            raise AppError(status_code=404, message="Evento no encontrado")
        _ensure_transition_allowed(
            existing.status,
            forbidden={EventStatus.CANCELLED, EventStatus.FINISHED},
            message="Evento no publicable",
        )
        _ensure_dates(existing.starts_at, existing.ends_at)

        if existing.status == EventStatus.PUBLISHED:
            return existing

        return await self._set_event_status(
            actor=actor,
            event=existing,
            status=EventStatus.PUBLISHED,
            action="event.published",
        )

    async def cancel_event(
        self,
        *,
        actor: UserPrincipal,
        event_id: UUID,
        payload: EventCancelRequest,
    ) -> EventResponse:
        existing = await self.repository.get_event(event_id)
        if existing is None:
            raise AppError(status_code=404, message="Evento no encontrado")
        _ensure_transition_allowed(
            existing.status,
            forbidden={EventStatus.FINISHED},
            message="Evento finalizado no cancelable",
        )

        if existing.status == EventStatus.CANCELLED:
            return existing

        return await self._set_event_status(
            actor=actor,
            event=existing,
            status=EventStatus.CANCELLED,
            action="event.cancelled",
            extra_metadata={"reason": payload.reason},
        )

    async def finish_event(
        self,
        *,
        actor: UserPrincipal,
        event_id: UUID,
    ) -> EventResponse:
        existing = await self.repository.get_event(event_id)
        if existing is None:
            raise AppError(status_code=404, message="Evento no encontrado")
        _ensure_transition_allowed(
            existing.status,
            forbidden={EventStatus.CANCELLED},
            message="Evento cancelado no finalizable",
        )

        if existing.status == EventStatus.FINISHED:
            return existing

        return await self._set_event_status(
            actor=actor,
            event=existing,
            status=EventStatus.FINISHED,
            action="event.finished",
        )

    async def register_current_user(
        self,
        *,
        actor: UserPrincipal,
        event_id: UUID,
    ) -> EventRegistrationResponse:
        event = await self.repository.get_event(event_id)
        if event is None:
            raise AppError(status_code=404, message="Evento no encontrado")
        if event.status != EventStatus.PUBLISHED:
            raise AppError(
                status_code=409,
                message="Evento no disponible para inscripcion",
            )

        existing = await self.repository.get_registration(
            event_id=event_id,
            user_id=actor.id,
        )
        if existing is not None and existing.status == RegistrationStatus.REGISTERED:
            raise AppError(status_code=409, message="Usuario ya inscrito")

        await self._ensure_capacity_available(event)

        try:
            if existing is not None and existing.status == RegistrationStatus.CANCELLED:
                registration = await self.repository.reactivate_registration(
                    event_id=event_id,
                    user_id=actor.id,
                )
                if registration is None:
                    raise AppError(status_code=404, message="Inscripcion no encontrada")
            else:
                registration = await self.repository.create_registration(
                    event_id=event_id,
                    user_id=actor.id,
                )
            await self.repository.commit()
            return registration
        except Exception:
            await self.repository.rollback()
            raise

    async def cancel_current_user_registration(
        self,
        *,
        actor: UserPrincipal,
        event_id: UUID,
    ) -> EventRegistrationResponse:
        registration = await self.repository.get_registration(
            event_id=event_id,
            user_id=actor.id,
        )
        if registration is None or registration.status != RegistrationStatus.REGISTERED:
            raise AppError(status_code=404, message="Inscripcion no encontrada")

        try:
            cancelled = await self.repository.cancel_registration(
                event_id=event_id,
                user_id=actor.id,
            )
            if cancelled is None:
                raise AppError(status_code=404, message="Inscripcion no encontrada")
            await self.repository.commit()
            return cancelled
        except Exception:
            await self.repository.rollback()
            raise

    async def record_attendance(
        self,
        *,
        actor: UserPrincipal,
        event_id: UUID,
        payload: EventAttendanceRequest,
    ) -> EventAttendanceResponse:
        event = await self.repository.get_event(event_id)
        if event is None:
            raise AppError(status_code=404, message="Evento no encontrado")
        registration = await self.repository.get_registration(
            event_id=event_id,
            user_id=payload.user_id,
        )
        if registration is None or registration.status != RegistrationStatus.REGISTERED:
            raise AppError(
                status_code=409,
                message="Usuario no inscrito en el evento",
            )

        existing = await self.repository.get_attendance(
            event_id=event_id,
            user_id=payload.user_id,
        )
        if existing is not None:
            return existing

        try:
            attendance = await self.repository.create_attendance(
                event_id=event_id,
                user_id=payload.user_id,
                checked_by=actor.id,
                notes=payload.notes,
            )
            await self._record_admin_action(
                actor_id=actor.id,
                entity_id=event_id,
                metadata={
                    "action": "event.attendance.recorded",
                    "user_id": str(payload.user_id),
                },
            )
            await self.repository.commit()
            return attendance
        except Exception:
            await self.repository.rollback()
            raise

    async def _set_event_status(
        self,
        *,
        actor: UserPrincipal,
        event: EventResponse,
        status: EventStatus,
        action: str,
        extra_metadata: dict[str, object] | None = None,
    ) -> EventResponse:
        try:
            updated = await self.repository.set_event_status(
                event_id=event.id,
                status=status,
            )
            if updated is None:
                raise AppError(status_code=404, message="Evento no encontrado")
            metadata: dict[str, object] = {
                "action": action,
                "old_status": event.status.value,
                "new_status": updated.status.value,
            }
            if extra_metadata:
                metadata.update(
                    {key: value for key, value in extra_metadata.items() if value}
                )
            await self._record_admin_action(
                actor_id=actor.id,
                entity_id=event.id,
                metadata=metadata,
            )
            await self.repository.commit()
            return updated
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

    async def _ensure_capacity_available(self, event: EventResponse) -> None:
        if event.capacity is None:
            return
        registered_count = await self.repository.count_registered(event.id)
        if registered_count < event.capacity:
            return
        raise AppError(status_code=409, message="Cupos agotados")

    async def _record_admin_action(
        self,
        *,
        actor_id: UUID,
        entity_id: UUID,
        metadata: dict[str, object],
    ) -> None:
        if self.auditor is None:
            return
        await self.auditor.record_administrative_action(
            actor_id=actor_id,
            entity_type="events",
            entity_id=entity_id,
            metadata=metadata,
        )


def create_event_service(db: AsyncSession) -> EventService:
    return EventService(DatabaseEventRepository(db), AuditService(db))


def _event_where(
    *,
    status: EventStatus | None,
    category_id: UUID | None,
    upcoming_only: bool,
) -> tuple[str, dict[str, Any]]:
    params: dict[str, Any] = {}
    conditions = ["e.deleted_at IS NULL"]
    if status is not None:
        conditions.append("e.status = CAST(:status AS event_status)")
        params["status"] = status.value
    if category_id is not None:
        conditions.append("e.category_id = :category_id")
        params["category_id"] = category_id
    if upcoming_only:
        conditions.append("e.starts_at >= now()")
    return " AND ".join(conditions), params


def _ensure_events_manage_permission(current_user: UserPrincipal | None) -> None:
    if current_user is None:
        raise AppError(status_code=401, message="No autenticado")
    if PermissionCode.EVENTS_MANAGE.value in set(current_user.permissions):
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


def _ensure_update_fields(fields: dict[str, Any]) -> None:
    if fields:
        return
    raise AppError(status_code=422, message="No hay campos para actualizar")


def _ensure_dates(starts_at: Any, ends_at: Any) -> None:
    if ends_at > starts_at:
        return
    raise AppError(
        status_code=422,
        message="Fecha de termino invalida",
        errors=[
            ErrorDetail(
                field="ends_at",
                detail="La fecha de termino debe ser posterior al inicio",
            )
        ],
    )


def _ensure_transition_allowed(
    status: EventStatus,
    *,
    forbidden: set[EventStatus],
    message: str,
) -> None:
    if status not in forbidden:
        return
    raise AppError(status_code=409, message=message)


def _normalize_event_status(value: object) -> EventStatus:
    return EventStatus(str(value).split(".")[-1].upper())


def _normalize_registration_status(value: object) -> RegistrationStatus:
    return RegistrationStatus(str(value).split(".")[-1].upper())


def _event_from_row(row: Any) -> EventResponse:
    return EventResponse(
        id=UUID(str(row["id"])),
        category_id=UUID(str(row["category_id"])) if row["category_id"] else None,
        category_name=row["category_name"],
        category_slug=row["category_slug"],
        name=str(row["name"]),
        description=str(row["description"]),
        starts_at=row["starts_at"],
        ends_at=row["ends_at"],
        location=row["location"],
        capacity=row["capacity"],
        registered_count=int(row["registered_count"] or 0),
        responsible_id=(
            UUID(str(row["responsible_id"])) if row["responsible_id"] else None
        ),
        responsible_name=row["responsible_name"],
        status=_normalize_event_status(row["status"]),
        published_at=row["published_at"],
        image_url=row["image_url"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _registration_from_row(row: Any) -> EventRegistrationResponse:
    return EventRegistrationResponse(
        id=UUID(str(row["id"])),
        event_id=UUID(str(row["event_id"])),
        user_id=UUID(str(row["user_id"])),
        status=_normalize_registration_status(row["status"]),
        registered_at=row["registered_at"],
        cancelled_at=row["cancelled_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _attendance_from_row(row: Any) -> EventAttendanceResponse:
    return EventAttendanceResponse(
        id=UUID(str(row["id"])),
        event_id=UUID(str(row["event_id"])),
        user_id=UUID(str(row["user_id"])),
        checked_in_at=row["checked_in_at"],
        checked_by=UUID(str(row["checked_by"])) if row["checked_by"] else None,
        notes=row["notes"],
        created_at=row["created_at"],
    )


_EVENT_SELECT = """
SELECT
    e.id,
    e.category_id,
    c.name AS category_name,
    c.slug AS category_slug,
    e.name,
    e.description,
    e.starts_at,
    e.ends_at,
    e.location,
    e.capacity,
    COALESCE(registered_counts.registered_count, 0) AS registered_count,
    e.responsible_id,
    u.name AS responsible_name,
    e.status,
    e.published_at,
    e.image_url,
    e.created_at,
    e.updated_at
FROM events e
LEFT JOIN event_categories c ON c.id = e.category_id
LEFT JOIN users u ON u.id = e.responsible_id
LEFT JOIN (
    SELECT event_id, count(*) AS registered_count
    FROM event_registrations
    WHERE status = 'REGISTERED'
    GROUP BY event_id
) registered_counts ON registered_counts.event_id = e.id
"""
