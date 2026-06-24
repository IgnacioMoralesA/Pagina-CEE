from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.backend.auth.dependencies import (
    optional_auth,
    require_auth,
    require_permissions,
)
from app.backend.auth.permissions import PermissionCode
from app.backend.auth.schemas import UserPrincipal
from app.backend.core.responses import ApiResponse, success_response
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
)
from app.backend.events.service import EventService


router = APIRouter()


@router.get("/events", response_model=ApiResponse[PaginatedResponse[EventResponse]])
async def list_events(
    status: EventStatus | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: UserPrincipal | None = Depends(optional_auth),
    event_service: EventService = Depends(get_event_service),
) -> ApiResponse[PaginatedResponse[EventResponse]]:
    events = await event_service.list_events(
        current_user=current_user,
        status=status,
        category_id=category_id,
        limit=limit,
        offset=offset,
    )
    return success_response(events, "Eventos obtenidos")


@router.get("/events/{event_id}", response_model=ApiResponse[EventResponse])
async def get_event(
    event_id: UUID,
    current_user: UserPrincipal | None = Depends(optional_auth),
    event_service: EventService = Depends(get_event_service),
) -> ApiResponse[EventResponse]:
    event = await event_service.get_event(
        event_id=event_id,
        current_user=current_user,
    )
    return success_response(event, "Evento obtenido")


@router.post("/events", response_model=ApiResponse[EventResponse], status_code=201)
async def create_event(
    payload: EventCreateRequest,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.EVENTS_MANAGE.value)
    ),
    event_service: EventService = Depends(get_event_service),
) -> ApiResponse[EventResponse]:
    event = await event_service.create_event(actor=current_user, payload=payload)
    return success_response(event, "Evento creado")


@router.patch("/events/{event_id}", response_model=ApiResponse[EventResponse])
async def update_event(
    event_id: UUID,
    payload: EventUpdateRequest,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.EVENTS_MANAGE.value)
    ),
    event_service: EventService = Depends(get_event_service),
) -> ApiResponse[EventResponse]:
    event = await event_service.update_event(
        actor=current_user,
        event_id=event_id,
        payload=payload,
    )
    return success_response(event, "Evento actualizado")


@router.post("/events/{event_id}/publish", response_model=ApiResponse[EventResponse])
async def publish_event(
    event_id: UUID,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.EVENTS_MANAGE.value)
    ),
    event_service: EventService = Depends(get_event_service),
) -> ApiResponse[EventResponse]:
    event = await event_service.publish_event(actor=current_user, event_id=event_id)
    return success_response(event, "Evento publicado")


@router.post("/events/{event_id}/cancel", response_model=ApiResponse[EventResponse])
async def cancel_event(
    event_id: UUID,
    payload: EventCancelRequest | None = None,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.EVENTS_MANAGE.value)
    ),
    event_service: EventService = Depends(get_event_service),
) -> ApiResponse[EventResponse]:
    event = await event_service.cancel_event(
        actor=current_user,
        event_id=event_id,
        payload=payload or EventCancelRequest(),
    )
    return success_response(event, "Evento cancelado")


@router.post("/events/{event_id}/finish", response_model=ApiResponse[EventResponse])
async def finish_event(
    event_id: UUID,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.EVENTS_MANAGE.value)
    ),
    event_service: EventService = Depends(get_event_service),
) -> ApiResponse[EventResponse]:
    event = await event_service.finish_event(actor=current_user, event_id=event_id)
    return success_response(event, "Evento finalizado")


@router.post(
    "/events/{event_id}/register",
    response_model=ApiResponse[EventRegistrationResponse],
    status_code=201,
)
async def register_event(
    event_id: UUID,
    current_user: UserPrincipal = Depends(require_auth),
    event_service: EventService = Depends(get_event_service),
) -> ApiResponse[EventRegistrationResponse]:
    registration = await event_service.register_current_user(
        actor=current_user,
        event_id=event_id,
    )
    return success_response(registration, "Inscripcion registrada")


@router.delete(
    "/events/{event_id}/registration",
    response_model=ApiResponse[EventRegistrationResponse],
)
async def cancel_event_registration(
    event_id: UUID,
    current_user: UserPrincipal = Depends(require_auth),
    event_service: EventService = Depends(get_event_service),
) -> ApiResponse[EventRegistrationResponse]:
    registration = await event_service.cancel_current_user_registration(
        actor=current_user,
        event_id=event_id,
    )
    return success_response(registration, "Inscripcion cancelada")


@router.post(
    "/events/{event_id}/attendance",
    response_model=ApiResponse[EventAttendanceResponse],
    status_code=201,
)
async def record_event_attendance(
    event_id: UUID,
    payload: EventAttendanceRequest,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.EVENTS_MANAGE.value)
    ),
    event_service: EventService = Depends(get_event_service),
) -> ApiResponse[EventAttendanceResponse]:
    attendance = await event_service.record_attendance(
        actor=current_user,
        event_id=event_id,
        payload=payload,
    )
    return success_response(attendance, "Asistencia registrada")
