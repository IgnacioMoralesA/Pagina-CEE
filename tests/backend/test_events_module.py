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
from app.backend.core.config import Settings
from app.backend.core.errors import AppError
from app.backend.events.dependencies import get_event_service
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
from app.backend.events.service import EventService
from app.backend.main import create_app


class StaticAuthContextValidator:
    def __init__(self, *, permissions: list[str] | None = None) -> None:
        self.permissions = permissions or []

    async def validate(self, _: str, claims: TokenClaims) -> UserPrincipal:
        return UserPrincipal(
            id=claims.user_id,
            session_id=claims.session_id,
            email=claims.email,
            name=claims.name,
            role=RoleCode.ADMIN,
            roles=[RoleCode.ADMIN],
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


class FakeEventRepository:
    def __init__(
        self,
        *,
        events: list[EventResponse] | None = None,
        registrations: list[EventRegistrationResponse] | None = None,
        attendance: list[EventAttendanceResponse] | None = None,
        category_exists: bool = True,
    ) -> None:
        self.events = {item.id: item for item in events or []}
        self.registrations = {
            (item.event_id, item.user_id): item for item in registrations or []
        }
        self.attendance = {(item.event_id, item.user_id): item for item in attendance or []}
        self.category_exists_value = category_exists
        self.committed = False
        self.rolled_back = False

    async def category_exists(self, category_id: UUID) -> bool:
        return self.category_exists_value

    async def list_events(
        self,
        *,
        status: EventStatus | None,
        category_id: UUID | None,
        upcoming_only: bool,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[EventResponse]:
        now = datetime.now(timezone.utc)
        items = [
            item
            for item in self.events.values()
            if (status is None or item.status == status)
            and (category_id is None or item.category_id == category_id)
            and (not upcoming_only or item.starts_at >= now)
        ]
        return PaginatedResponse[EventResponse](
            items=items[offset : offset + limit],
            total=len(items),
            limit=limit,
            offset=offset,
        )

    async def get_event(self, event_id: UUID) -> EventResponse | None:
        return self.events.get(event_id)

    async def create_event(
        self,
        *,
        actor_id: UUID,
        payload: EventCreateRequest,
    ) -> EventResponse:
        item = build_event_response(
            uuid4(),
            payload.name,
            status=EventStatus.PLANNED,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            description=payload.description,
            capacity=payload.capacity,
            responsible_id=actor_id,
        )
        self.events[item.id] = item
        return item

    async def update_event(
        self,
        *,
        event_id: UUID,
        fields: dict[str, object],
    ) -> EventResponse | None:
        item = self.events.get(event_id)
        if item is None:
            return None
        updated = item.model_copy(update=fields)
        self.events[event_id] = updated
        return updated

    async def set_event_status(
        self,
        *,
        event_id: UUID,
        status: EventStatus,
    ) -> EventResponse | None:
        item = self.events.get(event_id)
        if item is None:
            return None
        update = {"status": status}
        if status == EventStatus.PUBLISHED:
            update["published_at"] = datetime.now(timezone.utc)
        updated = item.model_copy(update=update)
        self.events[event_id] = updated
        return updated

    async def get_registration(
        self,
        *,
        event_id: UUID,
        user_id: UUID,
    ) -> EventRegistrationResponse | None:
        return self.registrations.get((event_id, user_id))

    async def count_registered(self, event_id: UUID) -> int:
        return sum(
            1
            for registration in self.registrations.values()
            if registration.event_id == event_id
            and registration.status == RegistrationStatus.REGISTERED
        )

    async def create_registration(
        self,
        *,
        event_id: UUID,
        user_id: UUID,
    ) -> EventRegistrationResponse:
        registration = build_registration_response(
            uuid4(),
            event_id,
            user_id,
            status=RegistrationStatus.REGISTERED,
        )
        self.registrations[(event_id, user_id)] = registration
        return registration

    async def reactivate_registration(
        self,
        *,
        event_id: UUID,
        user_id: UUID,
    ) -> EventRegistrationResponse | None:
        registration = self.registrations.get((event_id, user_id))
        if registration is None:
            return None
        updated = registration.model_copy(
            update={
                "status": RegistrationStatus.REGISTERED,
                "cancelled_at": None,
                "registered_at": datetime.now(timezone.utc),
            }
        )
        self.registrations[(event_id, user_id)] = updated
        return updated

    async def cancel_registration(
        self,
        *,
        event_id: UUID,
        user_id: UUID,
    ) -> EventRegistrationResponse | None:
        registration = self.registrations.get((event_id, user_id))
        if registration is None or registration.status != RegistrationStatus.REGISTERED:
            return None
        updated = registration.model_copy(
            update={
                "status": RegistrationStatus.CANCELLED,
                "cancelled_at": datetime.now(timezone.utc),
            }
        )
        self.registrations[(event_id, user_id)] = updated
        return updated

    async def get_attendance(
        self,
        *,
        event_id: UUID,
        user_id: UUID,
    ) -> EventAttendanceResponse | None:
        return self.attendance.get((event_id, user_id))

    async def create_attendance(
        self,
        *,
        event_id: UUID,
        user_id: UUID,
        checked_by: UUID,
        notes: str | None,
    ) -> EventAttendanceResponse:
        item = build_attendance_response(
            uuid4(),
            event_id,
            user_id,
            checked_by=checked_by,
            notes=notes,
        )
        self.attendance[(event_id, user_id)] = item
        return item

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def build_event_response(
    event_id: UUID,
    name: str,
    *,
    status: EventStatus,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    description: str = "Descripcion del evento",
    capacity: int | None = None,
    registered_count: int = 0,
    responsible_id: UUID | None = None,
) -> EventResponse:
    now = datetime.now(timezone.utc)
    start = starts_at or now + timedelta(days=7)
    end = ends_at or start + timedelta(hours=2)
    return EventResponse(
        id=event_id,
        category_id=None,
        category_name=None,
        category_slug=None,
        name=name,
        description=description,
        starts_at=start,
        ends_at=end,
        location="Auditorio",
        capacity=capacity,
        registered_count=registered_count,
        responsible_id=responsible_id or uuid4(),
        responsible_name="Admin Demo",
        status=status,
        published_at=now if status == EventStatus.PUBLISHED else None,
        image_url=None,
        created_at=now,
        updated_at=now,
    )


def build_registration_response(
    registration_id: UUID,
    event_id: UUID,
    user_id: UUID,
    *,
    status: RegistrationStatus,
) -> EventRegistrationResponse:
    now = datetime.now(timezone.utc)
    return EventRegistrationResponse(
        id=registration_id,
        event_id=event_id,
        user_id=user_id,
        status=status,
        registered_at=now,
        cancelled_at=now if status == RegistrationStatus.CANCELLED else None,
        created_at=now,
        updated_at=now,
    )


def build_attendance_response(
    attendance_id: UUID,
    event_id: UUID,
    user_id: UUID,
    *,
    checked_by: UUID,
    notes: str | None = None,
) -> EventAttendanceResponse:
    now = datetime.now(timezone.utc)
    return EventAttendanceResponse(
        id=attendance_id,
        event_id=event_id,
        user_id=user_id,
        checked_in_at=now,
        checked_by=checked_by,
        notes=notes,
        created_at=now,
    )


def build_actor(
    *,
    user_id: UUID | None = None,
    permissions: list[str] | None = None,
) -> UserPrincipal:
    return UserPrincipal(
        id=user_id or uuid4(),
        session_id=uuid4(),
        email="admin@example.edu",
        name="Admin Demo",
        role=RoleCode.ADMIN,
        roles=[RoleCode.ADMIN],
        permissions=permissions or [PermissionCode.EVENTS_MANAGE.value],
    )


def build_client(
    service: EventService,
    *,
    permissions: list[str] | None = None,
    user_id: UUID | None = None,
) -> tuple[TestClient, str, UUID]:
    settings = Settings(jwt_secret_key="unit-test-secret")
    resolved_user_id = user_id or uuid4()
    app = create_app(settings)
    app.dependency_overrides[get_event_service] = lambda: service
    app.dependency_overrides[get_auth_context_validator] = lambda: (
        StaticAuthContextValidator(permissions=permissions or [])
    )
    token, _ = create_access_token(
        user_id=resolved_user_id,
        session_id=uuid4(),
        email="admin@example.edu",
        name="Admin Demo",
        roles=[RoleCode.ADMIN],
        permissions=[],
        settings=settings,
    )
    return TestClient(app), token, resolved_user_id


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def event_payload() -> dict[str, str]:
    starts_at = datetime.now(timezone.utc) + timedelta(days=10)
    ends_at = starts_at + timedelta(hours=2)
    return {
        "name": "Asamblea general",
        "description": "Descripcion del evento",
        "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat(),
        "location": "Auditorio",
    }


def assert_standard_response_shape(payload: dict[str, object]) -> None:
    assert set(payload) == {"data", "message", "errors"}


def test_public_user_can_list_published_events() -> None:
    published = build_event_response(
        uuid4(),
        "Evento publico",
        status=EventStatus.PUBLISHED,
    )
    planned = build_event_response(uuid4(), "Planificado", status=EventStatus.PLANNED)
    service = EventService(FakeEventRepository(events=[published, planned]))
    client, _, _ = build_client(service)

    response = client.get("/api/v1/events")

    assert response.status_code == 200
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Eventos obtenidos"
    assert payload["data"]["total"] == 1
    assert payload["data"]["items"][0]["id"] == str(published.id)


def test_public_user_only_sees_published_upcoming_events() -> None:
    now = datetime.now(timezone.utc)
    upcoming = build_event_response(
        uuid4(),
        "Publicado proximo",
        status=EventStatus.PUBLISHED,
        starts_at=now + timedelta(days=2),
    )
    past = build_event_response(
        uuid4(),
        "Publicado pasado",
        status=EventStatus.PUBLISHED,
        starts_at=now - timedelta(days=2),
        ends_at=now - timedelta(days=2) + timedelta(hours=2),
    )
    cancelled = build_event_response(
        uuid4(),
        "Cancelado",
        status=EventStatus.CANCELLED,
    )
    finished = build_event_response(
        uuid4(),
        "Finalizado",
        status=EventStatus.FINISHED,
    )
    service = EventService(
        FakeEventRepository(events=[upcoming, past, cancelled, finished])
    )
    client, _, _ = build_client(service)

    response = client.get("/api/v1/events")

    assert response.status_code == 200
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["data"]["total"] == 1
    assert payload["data"]["items"][0]["id"] == str(upcoming.id)


def test_public_user_does_not_see_planned_events() -> None:
    planned = build_event_response(uuid4(), "Planificado", status=EventStatus.PLANNED)
    service = EventService(FakeEventRepository(events=[planned]))
    client, _, _ = build_client(service)

    list_response = client.get("/api/v1/events")
    detail_response = client.get(f"/api/v1/events/{planned.id}")

    assert list_response.status_code == 200
    assert list_response.json()["data"]["items"] == []
    assert detail_response.status_code == 404
    assert detail_response.json()["message"] == "Evento no encontrado"


@pytest.mark.parametrize("status", [EventStatus.CANCELLED, EventStatus.FINISHED])
def test_public_user_does_not_see_non_public_event_details(
    status: EventStatus,
) -> None:
    event = build_event_response(uuid4(), f"Evento {status.value}", status=status)
    service = EventService(FakeEventRepository(events=[event]))
    client, _, _ = build_client(service)

    response = client.get(f"/api/v1/events/{event.id}")

    assert response.status_code == 404
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Evento no encontrado"


@pytest.mark.parametrize(
    "status",
    [EventStatus.PLANNED, EventStatus.CANCELLED, EventStatus.FINISHED],
)
def test_admin_can_filter_non_public_events_with_permission(
    status: EventStatus,
) -> None:
    event = build_event_response(uuid4(), f"Evento {status.value}", status=status)
    service = EventService(FakeEventRepository(events=[event]))
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.EVENTS_MANAGE.value],
    )

    response = client.get(
        f"/api/v1/events?status={status.value}",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["data"]["total"] == 1
    assert payload["data"]["items"][0]["status"] == status.value


def test_authenticated_user_without_permission_cannot_filter_non_public_events() -> None:
    event = build_event_response(uuid4(), "Planificado", status=EventStatus.PLANNED)
    service = EventService(FakeEventRepository(events=[event]))
    client, token, _ = build_client(service, permissions=[])

    response = client.get(
        "/api/v1/events?status=PLANNED",
        headers=auth_header(token),
    )

    assert response.status_code == 403
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Permisos insuficientes"
    assert payload["errors"][0]["field"] == "permissions"


def test_admin_event_routes_require_session() -> None:
    event = build_event_response(uuid4(), "Planificado", status=EventStatus.PLANNED)
    service = EventService(FakeEventRepository(events=[event]))
    client, _, _ = build_client(
        service,
        permissions=[PermissionCode.EVENTS_MANAGE.value],
    )

    requests = [
        ("post", "/api/v1/events", event_payload()),
        ("patch", f"/api/v1/events/{event.id}", {"name": "Nuevo nombre"}),
        ("post", f"/api/v1/events/{event.id}/publish", None),
        ("post", f"/api/v1/events/{event.id}/cancel", {"reason": "Lluvia"}),
        ("post", f"/api/v1/events/{event.id}/finish", None),
        ("post", f"/api/v1/events/{event.id}/attendance", {"user_id": str(uuid4())}),
    ]

    for method, path, json_body in requests:
        response = client.request(method, path, json=json_body)
        payload = response.json()
        assert response.status_code == 401
        assert_standard_response_shape(payload)
        assert payload["message"] == "No autenticado"


def test_admin_event_routes_require_events_manage_permission() -> None:
    event = build_event_response(uuid4(), "Planificado", status=EventStatus.PLANNED)
    service = EventService(FakeEventRepository(events=[event]))
    client, token, _ = build_client(service, permissions=[])

    requests = [
        ("post", "/api/v1/events", event_payload()),
        ("patch", f"/api/v1/events/{event.id}", {"name": "Nuevo nombre"}),
        ("post", f"/api/v1/events/{event.id}/publish", None),
        ("post", f"/api/v1/events/{event.id}/cancel", {"reason": "Lluvia"}),
        ("post", f"/api/v1/events/{event.id}/finish", None),
        ("post", f"/api/v1/events/{event.id}/attendance", {"user_id": str(uuid4())}),
    ]

    for method, path, json_body in requests:
        response = client.request(method, path, headers=auth_header(token), json=json_body)
        payload = response.json()
        assert response.status_code == 403
        assert_standard_response_shape(payload)
        assert payload["message"] == "Permisos insuficientes"
        assert payload["errors"][0]["field"] == "permissions"


def test_user_without_session_cannot_create_event() -> None:
    service = EventService(FakeEventRepository())
    client, _, _ = build_client(service)

    response = client.post("/api/v1/events", json=event_payload())

    assert response.status_code == 401
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "No autenticado"


def test_user_without_permission_receives_403_in_admin_endpoint() -> None:
    service = EventService(FakeEventRepository())
    client, token, _ = build_client(service, permissions=[])

    response = client.post(
        "/api/v1/events",
        headers=auth_header(token),
        json=event_payload(),
    )

    assert response.status_code == 403
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Permisos insuficientes"


def test_user_with_permission_can_create_event() -> None:
    service = EventService(FakeEventRepository())
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.EVENTS_MANAGE.value],
    )

    response = client.post(
        "/api/v1/events",
        headers=auth_header(token),
        json=event_payload(),
    )

    assert response.status_code == 201
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Evento creado"
    assert payload["data"]["status"] == "PLANNED"


def test_user_with_permission_can_update_publish_cancel_finish_and_attend_via_routes() -> None:
    event_to_update = build_event_response(
        uuid4(),
        "Evento editable",
        status=EventStatus.PLANNED,
    )
    event_to_publish = build_event_response(
        uuid4(),
        "Evento publicable",
        status=EventStatus.PLANNED,
    )
    event_to_cancel = build_event_response(
        uuid4(),
        "Evento cancelable",
        status=EventStatus.PUBLISHED,
    )
    event_to_finish = build_event_response(
        uuid4(),
        "Evento finalizable",
        status=EventStatus.PUBLISHED,
    )
    attendance_user_id = uuid4()
    event_for_attendance = build_event_response(
        uuid4(),
        "Evento con asistencia",
        status=EventStatus.PUBLISHED,
    )
    registration = build_registration_response(
        uuid4(),
        event_for_attendance.id,
        attendance_user_id,
        status=RegistrationStatus.REGISTERED,
    )
    repository = FakeEventRepository(
        events=[
            event_to_update,
            event_to_publish,
            event_to_cancel,
            event_to_finish,
            event_for_attendance,
        ],
        registrations=[registration],
    )
    auditor = RecordingAuditor()
    service = EventService(repository, auditor)
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.EVENTS_MANAGE.value],
    )

    update_response = client.patch(
        f"/api/v1/events/{event_to_update.id}",
        headers=auth_header(token),
        json={"name": "Evento actualizado"},
    )
    publish_response = client.post(
        f"/api/v1/events/{event_to_publish.id}/publish",
        headers=auth_header(token),
    )
    cancel_response = client.post(
        f"/api/v1/events/{event_to_cancel.id}/cancel",
        headers=auth_header(token),
        json={"reason": "Lluvia"},
    )
    finish_response = client.post(
        f"/api/v1/events/{event_to_finish.id}/finish",
        headers=auth_header(token),
    )
    attendance_response = client.post(
        f"/api/v1/events/{event_for_attendance.id}/attendance",
        headers=auth_header(token),
        json={"user_id": str(attendance_user_id), "notes": "Presente"},
    )

    assert update_response.status_code == 200
    assert publish_response.status_code == 200
    assert cancel_response.status_code == 200
    assert finish_response.status_code == 200
    assert attendance_response.status_code == 201
    assert update_response.json()["data"]["name"] == "Evento actualizado"
    assert publish_response.json()["data"]["status"] == "PUBLISHED"
    assert publish_response.json()["data"]["published_at"] is not None
    assert cancel_response.json()["data"]["status"] == "CANCELLED"
    assert finish_response.json()["data"]["status"] == "FINISHED"
    assert attendance_response.json()["data"]["user_id"] == str(attendance_user_id)
    assert [event["metadata"]["action"] for event in auditor.events] == [
        "event.updated",
        "event.published",
        "event.cancelled",
        "event.finished",
        "event.attendance.recorded",
    ]
    assert auditor.events[2]["metadata"]["reason"] == "Lluvia"


def test_create_event_generates_administrative_audit() -> None:
    asyncio.run(_run_create_event_audit_check())


async def _run_create_event_audit_check() -> None:
    repository = FakeEventRepository()
    auditor = RecordingAuditor()
    service = EventService(repository, auditor)
    actor = build_actor()

    created = await service.create_event(
        actor=actor,
        payload=EventCreateRequest(**event_payload()),
    )

    assert repository.committed is True
    assert auditor.events == [
        {
            "actor_id": actor.id,
            "entity_type": "events",
            "entity_id": created.id,
            "metadata": {"action": "event.created", "status": "PLANNED"},
        }
    ]


def test_publish_and_cancel_event_change_status() -> None:
    asyncio.run(_run_publish_and_cancel_check())


async def _run_publish_and_cancel_check() -> None:
    event = build_event_response(uuid4(), "Planificado", status=EventStatus.PLANNED)
    repository = FakeEventRepository(events=[event])
    service = EventService(repository, RecordingAuditor())
    actor = build_actor()

    published = await service.publish_event(actor=actor, event_id=event.id)
    cancelled = await service.cancel_event(
        actor=actor,
        event_id=event.id,
        payload=EventCancelRequest(reason="Lluvia"),
    )

    assert published.status == EventStatus.PUBLISHED
    assert published.published_at is not None
    assert cancelled.status == EventStatus.CANCELLED


def test_finish_event_changes_status() -> None:
    asyncio.run(_run_finish_event_check())


async def _run_finish_event_check() -> None:
    event = build_event_response(uuid4(), "Publicado", status=EventStatus.PUBLISHED)
    repository = FakeEventRepository(events=[event])
    service = EventService(repository, RecordingAuditor())

    finished = await service.finish_event(actor=build_actor(), event_id=event.id)

    assert finished.status == EventStatus.FINISHED


def test_end_date_before_start_returns_error() -> None:
    starts_at = datetime.now(timezone.utc) + timedelta(days=2)
    ends_at = starts_at - timedelta(hours=1)
    service = EventService(FakeEventRepository())
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.EVENTS_MANAGE.value],
    )

    response = client.post(
        "/api/v1/events",
        headers=auth_header(token),
        json={
            "name": "Evento invalido",
            "description": "Descripcion",
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Solicitud invalida"


def test_update_event_rejects_end_before_existing_start() -> None:
    starts_at = datetime.now(timezone.utc) + timedelta(days=2)
    event = build_event_response(
        uuid4(),
        "Evento editable",
        status=EventStatus.PLANNED,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=2),
    )
    service = EventService(FakeEventRepository(events=[event]))
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.EVENTS_MANAGE.value],
    )

    response = client.patch(
        f"/api/v1/events/{event.id}",
        headers=auth_header(token),
        json={"ends_at": (starts_at - timedelta(minutes=1)).isoformat()},
    )

    assert response.status_code == 422
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Fecha de termino invalida"
    assert payload["errors"][0]["field"] == "ends_at"


def test_registration_routes_require_authentication() -> None:
    event = build_event_response(uuid4(), "Publicado", status=EventStatus.PUBLISHED)
    service = EventService(FakeEventRepository(events=[event]))
    client, _, _ = build_client(service)

    register_response = client.post(f"/api/v1/events/{event.id}/register")
    cancel_response = client.delete(f"/api/v1/events/{event.id}/registration")

    assert register_response.status_code == 401
    assert cancel_response.status_code == 401
    assert_standard_response_shape(register_response.json())
    assert_standard_response_shape(cancel_response.json())
    assert register_response.json()["message"] == "No autenticado"
    assert cancel_response.json()["message"] == "No autenticado"


def test_authenticated_user_can_register_to_published_event() -> None:
    user_id = uuid4()
    event = build_event_response(uuid4(), "Publicado", status=EventStatus.PUBLISHED)
    service = EventService(FakeEventRepository(events=[event]))
    client, token, _ = build_client(
        service,
        user_id=user_id,
        permissions=[PermissionCode.EVENTS_REGISTER.value],
    )

    response = client.post(
        f"/api/v1/events/{event.id}/register",
        headers=auth_header(token),
    )

    assert response.status_code == 201
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Inscripcion registrada"
    assert payload["data"]["user_id"] == str(user_id)
    assert payload["data"]["status"] == "REGISTERED"


def test_authenticated_user_without_event_permissions_can_register() -> None:
    user_id = uuid4()
    event = build_event_response(uuid4(), "Publicado", status=EventStatus.PUBLISHED)
    service = EventService(FakeEventRepository(events=[event]))
    client, token, _ = build_client(service, user_id=user_id, permissions=[])

    response = client.post(
        f"/api/v1/events/{event.id}/register",
        headers=auth_header(token),
    )

    assert response.status_code == 201
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["data"]["user_id"] == str(user_id)
    assert payload["data"]["status"] == "REGISTERED"


def test_user_cannot_register_twice() -> None:
    asyncio.run(_run_duplicate_registration_check())


async def _run_duplicate_registration_check() -> None:
    user_id = uuid4()
    event = build_event_response(uuid4(), "Publicado", status=EventStatus.PUBLISHED)
    registration = build_registration_response(
        uuid4(),
        event.id,
        user_id,
        status=RegistrationStatus.REGISTERED,
    )
    service = EventService(
        FakeEventRepository(events=[event], registrations=[registration])
    )

    with pytest.raises(AppError) as exc_info:
        await service.register_current_user(
            actor=build_actor(user_id=user_id),
            event_id=event.id,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.message == "Usuario ya inscrito"


def test_user_cannot_register_when_capacity_is_full() -> None:
    asyncio.run(_run_capacity_check())


async def _run_capacity_check() -> None:
    existing_user_id = uuid4()
    event = build_event_response(
        uuid4(),
        "Publicado",
        status=EventStatus.PUBLISHED,
        capacity=1,
    )
    registration = build_registration_response(
        uuid4(),
        event.id,
        existing_user_id,
        status=RegistrationStatus.REGISTERED,
    )
    service = EventService(
        FakeEventRepository(events=[event], registrations=[registration])
    )

    with pytest.raises(AppError) as exc_info:
        await service.register_current_user(
            actor=build_actor(user_id=uuid4()),
            event_id=event.id,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.message == "Cupos agotados"


def test_user_cannot_register_to_unpublished_event() -> None:
    asyncio.run(_run_unpublished_registration_check())


async def _run_unpublished_registration_check() -> None:
    event = build_event_response(uuid4(), "Planificado", status=EventStatus.PLANNED)
    service = EventService(FakeEventRepository(events=[event]))

    with pytest.raises(AppError) as exc_info:
        await service.register_current_user(
            actor=build_actor(user_id=uuid4()),
            event_id=event.id,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.message == "Evento no disponible para inscripcion"


def test_user_can_cancel_own_registration() -> None:
    user_id = uuid4()
    event = build_event_response(uuid4(), "Publicado", status=EventStatus.PUBLISHED)
    registration = build_registration_response(
        uuid4(),
        event.id,
        user_id,
        status=RegistrationStatus.REGISTERED,
    )
    service = EventService(
        FakeEventRepository(events=[event], registrations=[registration])
    )
    client, token, _ = build_client(service, user_id=user_id)

    response = client.delete(
        f"/api/v1/events/{event.id}/registration",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Inscripcion cancelada"
    assert payload["data"]["status"] == "CANCELLED"
    assert payload["data"]["user_id"] == str(user_id)


def test_cancel_registration_does_not_affect_other_users() -> None:
    user_id = uuid4()
    other_user_id = uuid4()
    event = build_event_response(uuid4(), "Publicado", status=EventStatus.PUBLISHED)
    own_registration = build_registration_response(
        uuid4(),
        event.id,
        user_id,
        status=RegistrationStatus.REGISTERED,
    )
    other_registration = build_registration_response(
        uuid4(),
        event.id,
        other_user_id,
        status=RegistrationStatus.REGISTERED,
    )
    repository = FakeEventRepository(
        events=[event],
        registrations=[own_registration, other_registration],
    )
    service = EventService(repository)
    client, token, _ = build_client(service, user_id=user_id)

    response = client.delete(
        f"/api/v1/events/{event.id}/registration",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert repository.registrations[(event.id, user_id)].status == (
        RegistrationStatus.CANCELLED
    )
    assert repository.registrations[(event.id, other_user_id)].status == (
        RegistrationStatus.REGISTERED
    )


def test_attendance_requires_administrative_permission() -> None:
    event = build_event_response(uuid4(), "Publicado", status=EventStatus.PUBLISHED)
    service = EventService(FakeEventRepository(events=[event]))
    client, token, _ = build_client(service, permissions=[])

    response = client.post(
        f"/api/v1/events/{event.id}/attendance",
        headers=auth_header(token),
        json={"user_id": str(uuid4())},
    )

    assert response.status_code == 403
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Permisos insuficientes"


def test_attendance_requires_previous_registration() -> None:
    asyncio.run(_run_attendance_without_registration_check())


async def _run_attendance_without_registration_check() -> None:
    event = build_event_response(uuid4(), "Publicado", status=EventStatus.PUBLISHED)
    service = EventService(FakeEventRepository(events=[event]))

    with pytest.raises(AppError) as exc_info:
        await service.record_attendance(
            actor=build_actor(),
            event_id=event.id,
            payload=EventAttendanceRequest(user_id=uuid4()),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.message == "Usuario no inscrito en el evento"


def test_record_attendance_generates_administrative_audit() -> None:
    asyncio.run(_run_attendance_audit_check())


async def _run_attendance_audit_check() -> None:
    user_id = uuid4()
    event = build_event_response(uuid4(), "Publicado", status=EventStatus.PUBLISHED)
    registration = build_registration_response(
        uuid4(),
        event.id,
        user_id,
        status=RegistrationStatus.REGISTERED,
    )
    repository = FakeEventRepository(events=[event], registrations=[registration])
    auditor = RecordingAuditor()
    service = EventService(repository, auditor)
    actor = build_actor()

    attendance = await service.record_attendance(
        actor=actor,
        event_id=event.id,
        payload=EventAttendanceRequest(user_id=user_id, notes="Presente"),
    )

    assert attendance.user_id == user_id
    assert repository.committed is True
    assert auditor.events == [
        {
            "actor_id": actor.id,
            "entity_type": "events",
            "entity_id": event.id,
            "metadata": {
                "action": "event.attendance.recorded",
                "user_id": str(user_id),
            },
        }
    ]
