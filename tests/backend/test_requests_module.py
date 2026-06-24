from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.backend.auth.dependencies import get_auth_context_validator
from app.backend.auth.jwt import create_access_token
from app.backend.auth.permissions import PermissionCode, RoleCode
from app.backend.auth.schemas import TokenClaims, UserPrincipal
from app.backend.core.config import Settings
from app.backend.core.errors import AppError
from app.backend.main import create_app
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
    RequestPriority,
    RequestRejectRequest,
    RequestStatus,
    RequestStatusHistoryResponse,
    RequestUpdateRequest,
    StudentRequestResponse,
)
from app.backend.student_requests.service import StudentRequestService


class StaticAuthContextValidator:
    def __init__(self, *, permissions: list[str] | None = None) -> None:
        self.permissions = permissions or []

    async def validate(self, _: str, claims: TokenClaims) -> UserPrincipal:
        return UserPrincipal(
            id=claims.user_id,
            session_id=claims.session_id,
            email=claims.email,
            name=claims.name,
            role=RoleCode.STUDENT,
            roles=[RoleCode.STUDENT],
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


class FakeStudentRequestRepository:
    def __init__(
        self,
        *,
        requests: list[StudentRequestResponse] | None = None,
        category_exists: bool = True,
    ) -> None:
        self.requests = {item.id: item for item in requests or []}
        self.category_exists_value = category_exists
        self.committed = False
        self.rolled_back = False

    async def category_exists(self, category_id: UUID) -> bool:
        return self.category_exists_value

    async def list_requests(
        self,
        *,
        requester_id: UUID | None,
        status: RequestStatus | None,
        category_id: UUID | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[StudentRequestResponse]:
        items = [
            item
            for item in self.requests.values()
            if (requester_id is None or item.requester_id == requester_id)
            and (status is None or item.status == status)
            and (category_id is None or item.category_id == category_id)
        ]
        return PaginatedResponse[StudentRequestResponse](
            items=items[offset : offset + limit],
            total=len(items),
            limit=limit,
            offset=offset,
        )

    async def get_request(self, request_id: UUID) -> StudentRequestResponse | None:
        return self.requests.get(request_id)

    async def create_request(
        self,
        *,
        requester_id: UUID,
        payload: RequestCreateRequest,
    ) -> StudentRequestResponse:
        item = build_request_response(
            uuid4(),
            requester_id=requester_id,
            title=payload.title,
            description=payload.description,
            status=RequestStatus.SUBMITTED,
            priority=payload.priority,
            category_id=payload.category_id,
        )
        self.requests[item.id] = item
        return item

    async def update_request(
        self,
        *,
        request_id: UUID,
        fields: dict[str, object],
    ) -> StudentRequestResponse | None:
        item = self.requests.get(request_id)
        if item is None:
            return None
        update = dict(fields)
        update.pop("resolved_at", None)
        update.pop("closed_at", None)
        if "status" in update:
            update["status"] = RequestStatus(str(update["status"]))
        if "priority" in update:
            update["priority"] = RequestPriority(str(update["priority"]))
        if "resolved_at" in fields:
            update["resolved_at"] = datetime.now(timezone.utc)
        if "closed_at" in fields:
            update["closed_at"] = datetime.now(timezone.utc)
        updated = item.model_copy(update=update)
        self.requests[request_id] = updated
        return updated

    async def add_status_history(
        self,
        *,
        request_id: UUID,
        old_status: RequestStatus | None,
        new_status: RequestStatus,
        changed_by: UUID,
        comment: str | None,
    ) -> RequestStatusHistoryResponse:
        item = self.requests[request_id]
        history = build_history_response(
            uuid4(),
            request_id=request_id,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            comment=comment,
        )
        self.requests[request_id] = item.model_copy(
            update={"status_history": [*item.status_history, history]}
        )
        return history

    async def add_comment(
        self,
        *,
        request_id: UUID,
        author_id: UUID,
        body: str,
        is_internal: bool,
    ) -> RequestCommentResponse:
        item = self.requests[request_id]
        comment = build_comment_response(
            uuid4(),
            request_id=request_id,
            author_id=author_id,
            body=body,
            is_internal=is_internal,
        )
        self.requests[request_id] = item.model_copy(
            update={"comments": [*item.comments, comment]}
        )
        return comment

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def build_request_response(
    request_id: UUID,
    *,
    requester_id: UUID,
    title: str = "Solicitud demo",
    description: str = "Descripcion de la solicitud",
    status: RequestStatus = RequestStatus.SUBMITTED,
    priority: RequestPriority = RequestPriority.MEDIUM,
    category_id: UUID | None = None,
    assigned_to: UUID | None = None,
    comments: list[RequestCommentResponse] | None = None,
    history: list[RequestStatusHistoryResponse] | None = None,
) -> StudentRequestResponse:
    now = datetime.now(timezone.utc)
    return StudentRequestResponse(
        id=request_id,
        requester_id=requester_id,
        requester_name="Estudiante Demo",
        category_id=category_id,
        category_name=None,
        category_slug=None,
        title=title,
        description=description,
        status=status,
        priority=priority,
        assigned_to=assigned_to,
        assigned_to_name=None,
        resolution=None,
        resolved_at=now if status in {RequestStatus.APPROVED, RequestStatus.REJECTED} else None,
        closed_at=now if status == RequestStatus.CLOSED else None,
        created_at=now,
        updated_at=now,
        status_history=history or [],
        comments=comments or [],
    )


def build_history_response(
    history_id: UUID,
    *,
    request_id: UUID,
    old_status: RequestStatus | None,
    new_status: RequestStatus,
    changed_by: UUID,
    comment: str | None,
) -> RequestStatusHistoryResponse:
    return RequestStatusHistoryResponse(
        id=history_id,
        request_id=request_id,
        old_status=old_status,
        new_status=new_status,
        changed_by=changed_by,
        comment=comment,
        created_at=datetime.now(timezone.utc),
    )


def build_comment_response(
    comment_id: UUID,
    *,
    request_id: UUID,
    author_id: UUID,
    body: str = "Comentario",
    is_internal: bool = False,
) -> RequestCommentResponse:
    now = datetime.now(timezone.utc)
    return RequestCommentResponse(
        id=comment_id,
        request_id=request_id,
        author_id=author_id,
        author_name="Usuario Demo",
        body=body,
        is_internal=is_internal,
        created_at=now,
        updated_at=now,
    )


def build_actor(
    *,
    user_id: UUID | None = None,
    permissions: list[str] | None = None,
) -> UserPrincipal:
    return UserPrincipal(
        id=user_id or uuid4(),
        session_id=uuid4(),
        email="usuario@example.edu",
        name="Usuario Demo",
        role=RoleCode.STUDENT,
        roles=[RoleCode.STUDENT],
        permissions=permissions or [],
    )


def build_client(
    service: StudentRequestService,
    *,
    permissions: list[str] | None = None,
    user_id: UUID | None = None,
) -> tuple[TestClient, str, UUID]:
    settings = Settings(jwt_secret_key="unit-test-secret")
    resolved_user_id = user_id or uuid4()
    app = create_app(settings)
    app.dependency_overrides[get_student_request_service] = lambda: service
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


def request_payload() -> dict[str, str]:
    return {
        "title": "Certificado",
        "description": "Necesito apoyo con certificado",
    }


def assert_standard_response_shape(payload: dict[str, object]) -> None:
    assert set(payload) == {"data", "message", "errors"}


def test_authenticated_user_can_create_request() -> None:
    service = StudentRequestService(FakeStudentRequestRepository())
    client, token, user_id = build_client(
        service,
        permissions=[PermissionCode.REQUESTS_CREATE.value],
    )

    response = client.post(
        "/api/v1/requests",
        headers=auth_header(token),
        json=request_payload(),
    )

    assert response.status_code == 201
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Solicitud creada"
    assert payload["data"]["requester_id"] == str(user_id)
    assert payload["data"]["status"] == "SUBMITTED"


def test_created_request_has_initial_status_history() -> None:
    asyncio.run(_run_create_history_check())


async def _run_create_history_check() -> None:
    repository = FakeStudentRequestRepository()
    service = StudentRequestService(repository)
    actor = build_actor()

    created = await service.create_request(
        actor=actor,
        payload=RequestCreateRequest(**request_payload()),
    )

    assert repository.committed is True
    assert created.status == RequestStatus.SUBMITTED
    assert created.status_history[0].old_status is None
    assert created.status_history[0].new_status == RequestStatus.SUBMITTED
    assert created.status_history[0].changed_by == actor.id


def test_student_lists_only_own_requests() -> None:
    owner_id = uuid4()
    other_id = uuid4()
    own = build_request_response(uuid4(), requester_id=owner_id, title="Propia")
    other = build_request_response(uuid4(), requester_id=other_id, title="Ajena")
    service = StudentRequestService(
        FakeStudentRequestRepository(requests=[own, other])
    )
    client, token, _ = build_client(service, user_id=owner_id)

    response = client.get("/api/v1/requests", headers=auth_header(token))

    assert response.status_code == 200
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["data"]["total"] == 1
    assert payload["data"]["items"][0]["id"] == str(own.id)


def test_student_cannot_see_other_student_request() -> None:
    requester_id = uuid4()
    other = build_request_response(uuid4(), requester_id=requester_id)
    service = StudentRequestService(FakeStudentRequestRepository(requests=[other]))
    client, token, _ = build_client(service, user_id=uuid4())

    response = client.get(
        f"/api/v1/requests/{other.id}",
        headers=auth_header(token),
    )

    assert response.status_code == 404
    assert response.json()["message"] == "Solicitud no encontrada"


def test_user_without_session_cannot_create_request() -> None:
    service = StudentRequestService(FakeStudentRequestRepository())
    client, _, _ = build_client(
        service,
        permissions=[PermissionCode.REQUESTS_CREATE.value],
    )

    response = client.post("/api/v1/requests", json=request_payload())

    assert response.status_code == 401
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "No autenticado"


def test_user_without_requests_create_permission_cannot_create_request() -> None:
    service = StudentRequestService(FakeStudentRequestRepository())
    client, token, _ = build_client(service, permissions=[])

    response = client.post(
        "/api/v1/requests",
        headers=auth_header(token),
        json=request_payload(),
    )

    assert response.status_code == 403
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Permisos insuficientes"


def test_user_without_permission_cannot_list_all_requests() -> None:
    request = build_request_response(uuid4(), requester_id=uuid4())
    service = StudentRequestService(FakeStudentRequestRepository(requests=[request]))
    client, token, _ = build_client(service, permissions=[])

    response = client.get(
        "/api/v1/requests?scope=all",
        headers=auth_header(token),
    )

    assert response.status_code == 403
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Permisos insuficientes"


@pytest.mark.parametrize(
    ("query", "expected_message"),
    [
        ("status=SUBMITTED", "Permisos insuficientes"),
        (f"category_id={uuid4()}", "Permisos insuficientes"),
    ],
)
def test_user_without_permission_cannot_use_administrative_filters(
    query: str,
    expected_message: str,
) -> None:
    request = build_request_response(uuid4(), requester_id=uuid4())
    service = StudentRequestService(FakeStudentRequestRepository(requests=[request]))
    client, token, _ = build_client(service, permissions=[])

    response = client.get(
        f"/api/v1/requests?{query}",
        headers=auth_header(token),
    )

    assert response.status_code == 403
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == expected_message


def test_user_with_manage_permission_can_list_all_requests() -> None:
    first = build_request_response(uuid4(), requester_id=uuid4())
    second = build_request_response(uuid4(), requester_id=uuid4())
    service = StudentRequestService(
        FakeStudentRequestRepository(requests=[first, second])
    )
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.REQUESTS_MANAGE.value],
    )

    response = client.get(
        "/api/v1/requests?scope=all",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["total"] == 2


def test_user_with_manage_permission_can_filter_all_requests() -> None:
    category_id = uuid4()
    matching = build_request_response(
        uuid4(),
        requester_id=uuid4(),
        status=RequestStatus.OBSERVED,
        category_id=category_id,
    )
    other = build_request_response(
        uuid4(),
        requester_id=uuid4(),
        status=RequestStatus.SUBMITTED,
        category_id=uuid4(),
    )
    service = StudentRequestService(
        FakeStudentRequestRepository(requests=[matching, other])
    )
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.REQUESTS_MANAGE.value],
    )

    response = client.get(
        f"/api/v1/requests?scope=all&status=OBSERVED&category_id={category_id}",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["data"]["total"] == 1
    assert payload["data"]["items"][0]["id"] == str(matching.id)


def test_student_can_edit_own_submitted_request() -> None:
    owner_id = uuid4()
    student_request = build_request_response(uuid4(), requester_id=owner_id)
    service = StudentRequestService(
        FakeStudentRequestRepository(requests=[student_request])
    )
    client, token, _ = build_client(service, user_id=owner_id)

    response = client.patch(
        f"/api/v1/requests/{student_request.id}",
        headers=auth_header(token),
        json={"title": "Titulo editado"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Solicitud actualizada"
    assert payload["data"]["title"] == "Titulo editado"


def test_student_can_edit_own_observed_request() -> None:
    owner_id = uuid4()
    student_request = build_request_response(
        uuid4(),
        requester_id=owner_id,
        status=RequestStatus.OBSERVED,
    )
    service = StudentRequestService(
        FakeStudentRequestRepository(requests=[student_request])
    )
    client, token, _ = build_client(service, user_id=owner_id)

    response = client.patch(
        f"/api/v1/requests/{student_request.id}",
        headers=auth_header(token),
        json={"description": "Descripcion corregida"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["data"]["description"] == "Descripcion corregida"


def test_student_cannot_edit_closed_request() -> None:
    owner_id = uuid4()
    student_request = build_request_response(
        uuid4(),
        requester_id=owner_id,
        status=RequestStatus.CLOSED,
    )
    service = StudentRequestService(
        FakeStudentRequestRepository(requests=[student_request])
    )

    with pytest.raises(AppError) as exc_info:
        asyncio.run(
            service.update_request(
                actor=build_actor(user_id=owner_id),
                request_id=student_request.id,
                payload=RequestUpdateRequest(title="Nuevo titulo"),
            )
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.message == "Solicitud no editable"


@pytest.mark.parametrize(
    "status",
    [RequestStatus.APPROVED, RequestStatus.REJECTED],
)
def test_student_cannot_edit_terminal_request_states(status: RequestStatus) -> None:
    owner_id = uuid4()
    student_request = build_request_response(
        uuid4(),
        requester_id=owner_id,
        status=status,
    )
    service = StudentRequestService(
        FakeStudentRequestRepository(requests=[student_request])
    )

    with pytest.raises(AppError) as exc_info:
        asyncio.run(
            service.update_request(
                actor=build_actor(user_id=owner_id),
                request_id=student_request.id,
                payload=RequestUpdateRequest(description="Cambio indebido"),
            )
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.message == "Solicitud no editable"


def test_student_cannot_update_administrative_fields() -> None:
    owner_id = uuid4()
    student_request = build_request_response(uuid4(), requester_id=owner_id)
    service = StudentRequestService(
        FakeStudentRequestRepository(requests=[student_request])
    )

    with pytest.raises(AppError) as exc_info:
        asyncio.run(
            service.update_request(
                actor=build_actor(user_id=owner_id),
                request_id=student_request.id,
                payload=RequestUpdateRequest(assigned_to=uuid4()),
            )
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.message == "Permisos insuficientes"


def test_administrative_patch_updates_admin_fields_and_audits() -> None:
    asyncio.run(_run_admin_patch_check())


async def _run_admin_patch_check() -> None:
    student_request = build_request_response(uuid4(), requester_id=uuid4())
    repository = FakeStudentRequestRepository(requests=[student_request])
    auditor = RecordingAuditor()
    service = StudentRequestService(repository, auditor)
    actor = build_actor(permissions=[PermissionCode.REQUESTS_MANAGE.value])
    responsible_id = uuid4()

    updated = await service.update_request(
        actor=actor,
        request_id=student_request.id,
        payload=RequestUpdateRequest(
            assigned_to=responsible_id,
            resolution="Derivada a secretaria",
        ),
    )

    assert updated.assigned_to == responsible_id
    assert updated.resolution == "Derivada a secretaria"
    assert auditor.events[-1]["entity_type"] == "requests"
    assert auditor.events[-1]["metadata"]["action"] == "request.updated"
    assert auditor.events[-1]["metadata"]["changed_fields"] == [
        "assigned_to",
        "resolution",
    ]


def test_administrative_user_can_assign_responsible_and_audit() -> None:
    asyncio.run(_run_assign_check())


async def _run_assign_check() -> None:
    student_request = build_request_response(uuid4(), requester_id=uuid4())
    repository = FakeStudentRequestRepository(requests=[student_request])
    auditor = RecordingAuditor()
    service = StudentRequestService(repository, auditor)
    actor = build_actor(permissions=[PermissionCode.REQUESTS_MANAGE.value])
    responsible_id = uuid4()

    assigned = await service.assign_request(
        actor=actor,
        request_id=student_request.id,
        payload=RequestAssignRequest(assigned_to=responsible_id),
    )

    assert assigned.assigned_to == responsible_id
    assert assigned.status == RequestStatus.IN_REVIEW
    assert assigned.status_history[-1].new_status == RequestStatus.IN_REVIEW
    assert auditor.events[-1]["metadata"]["action"] == "request.assigned"


def test_administrative_request_routes_require_session() -> None:
    student_request = build_request_response(uuid4(), requester_id=uuid4())
    service = StudentRequestService(
        FakeStudentRequestRepository(requests=[student_request])
    )
    client, _, _ = build_client(
        service,
        permissions=[PermissionCode.REQUESTS_MANAGE.value],
    )
    requests = [
        ("post", f"/api/v1/requests/{student_request.id}/assign", {"assigned_to": str(uuid4())}),
        ("post", f"/api/v1/requests/{student_request.id}/observe", {"reason": "Falta antecedente"}),
        ("post", f"/api/v1/requests/{student_request.id}/approve", {"resolution": "Aprobada"}),
        ("post", f"/api/v1/requests/{student_request.id}/reject", {"reason": "No cumple"}),
        ("post", f"/api/v1/requests/{student_request.id}/close", {"comment": "Cierre"}),
    ]

    for method, path, json_body in requests:
        response = getattr(client, method)(path, json=json_body)

        assert response.status_code == 401
        payload = response.json()
        assert_standard_response_shape(payload)
        assert payload["message"] == "No autenticado"


def test_administrative_request_routes_require_manage_permission() -> None:
    student_request = build_request_response(uuid4(), requester_id=uuid4())
    service = StudentRequestService(
        FakeStudentRequestRepository(requests=[student_request])
    )
    client, token, _ = build_client(service, permissions=[])
    requests = [
        ("post", f"/api/v1/requests/{student_request.id}/assign", {"assigned_to": str(uuid4())}),
        ("post", f"/api/v1/requests/{student_request.id}/observe", {"reason": "Falta antecedente"}),
        ("post", f"/api/v1/requests/{student_request.id}/approve", {"resolution": "Aprobada"}),
        ("post", f"/api/v1/requests/{student_request.id}/reject", {"reason": "No cumple"}),
        ("post", f"/api/v1/requests/{student_request.id}/close", {"comment": "Cierre"}),
    ]

    for method, path, json_body in requests:
        response = getattr(client, method)(
            path,
            headers=auth_header(token),
            json=json_body,
        )

        assert response.status_code == 403
        payload = response.json()
        assert_standard_response_shape(payload)
        assert payload["message"] == "Permisos insuficientes"


def test_administrative_user_can_observe_with_reason_and_history() -> None:
    asyncio.run(_run_observe_check())


async def _run_observe_check() -> None:
    student_request = build_request_response(uuid4(), requester_id=uuid4())
    repository = FakeStudentRequestRepository(requests=[student_request])
    auditor = RecordingAuditor()
    service = StudentRequestService(repository, auditor)
    actor = build_actor(permissions=[PermissionCode.REQUESTS_MANAGE.value])

    observed = await service.observe_request(
        actor=actor,
        request_id=student_request.id,
        payload=RequestObserveRequest(reason="Falta antecedente"),
    )

    assert observed.status == RequestStatus.OBSERVED
    assert observed.status_history[-1].new_status == RequestStatus.OBSERVED
    assert observed.status_history[-1].comment == "Falta antecedente"
    assert auditor.events[-1]["metadata"]["action"] == "request.observed"


@pytest.mark.parametrize(
    ("path_suffix", "payload"),
    [
        ("observe", {"reason": "   "}),
        ("reject", {"reason": ""}),
    ],
)
def test_reason_required_for_observe_and_reject_routes(
    path_suffix: str,
    payload: dict[str, str],
) -> None:
    student_request = build_request_response(uuid4(), requester_id=uuid4())
    service = StudentRequestService(
        FakeStudentRequestRepository(requests=[student_request])
    )
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.REQUESTS_MANAGE.value],
    )

    response = client.post(
        f"/api/v1/requests/{student_request.id}/{path_suffix}",
        headers=auth_header(token),
        json=payload,
    )

    assert response.status_code == 422
    assert_standard_response_shape(response.json())


def test_administrative_user_can_approve_with_history_and_audit() -> None:
    asyncio.run(_run_approve_check())


async def _run_approve_check() -> None:
    student_request = build_request_response(uuid4(), requester_id=uuid4())
    repository = FakeStudentRequestRepository(requests=[student_request])
    auditor = RecordingAuditor()
    service = StudentRequestService(repository, auditor)
    actor = build_actor(permissions=[PermissionCode.REQUESTS_MANAGE.value])

    approved = await service.approve_request(
        actor=actor,
        request_id=student_request.id,
        payload=RequestApproveRequest(resolution="Aprobada"),
    )

    assert approved.status == RequestStatus.APPROVED
    assert approved.status_history[-1].new_status == RequestStatus.APPROVED
    assert auditor.events[-1]["metadata"]["action"] == "request.approved"


def test_administrative_user_can_reject_with_reason_history_and_audit() -> None:
    asyncio.run(_run_reject_check())


async def _run_reject_check() -> None:
    student_request = build_request_response(uuid4(), requester_id=uuid4())
    repository = FakeStudentRequestRepository(requests=[student_request])
    auditor = RecordingAuditor()
    service = StudentRequestService(repository, auditor)
    actor = build_actor(permissions=[PermissionCode.REQUESTS_MANAGE.value])

    rejected = await service.reject_request(
        actor=actor,
        request_id=student_request.id,
        payload=RequestRejectRequest(reason="No cumple requisitos"),
    )

    assert rejected.status == RequestStatus.REJECTED
    assert rejected.status_history[-1].new_status == RequestStatus.REJECTED
    assert rejected.status_history[-1].comment == "No cumple requisitos"
    assert auditor.events[-1]["metadata"]["action"] == "request.rejected"


def test_student_cannot_execute_administrative_request_actions() -> None:
    student_request = build_request_response(uuid4(), requester_id=uuid4())
    service = StudentRequestService(
        FakeStudentRequestRepository(requests=[student_request])
    )

    with pytest.raises(AppError) as exc_info:
        asyncio.run(
            service.assign_request(
                actor=build_actor(),
                request_id=student_request.id,
                payload=RequestAssignRequest(assigned_to=uuid4()),
            )
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.message == "Permisos insuficientes"


def test_administrative_user_can_close_with_history_and_audit() -> None:
    asyncio.run(_run_close_check())


async def _run_close_check() -> None:
    student_request = build_request_response(
        uuid4(),
        requester_id=uuid4(),
        status=RequestStatus.APPROVED,
    )
    repository = FakeStudentRequestRepository(requests=[student_request])
    auditor = RecordingAuditor()
    service = StudentRequestService(repository, auditor)
    actor = build_actor(permissions=[PermissionCode.REQUESTS_MANAGE.value])

    closed = await service.close_request(
        actor=actor,
        request_id=student_request.id,
        payload=RequestCloseRequest(comment="Caso finalizado"),
    )

    assert closed.status == RequestStatus.CLOSED
    assert closed.status_history[-1].new_status == RequestStatus.CLOSED
    assert closed.status_history[-1].comment == "Caso finalizado"
    assert auditor.events[-1]["metadata"]["action"] == "request.closed"


def test_cannot_approve_closed_request() -> None:
    student_request = build_request_response(
        uuid4(),
        requester_id=uuid4(),
        status=RequestStatus.CLOSED,
    )
    service = StudentRequestService(
        FakeStudentRequestRepository(requests=[student_request])
    )

    with pytest.raises(AppError) as exc_info:
        asyncio.run(
            service.approve_request(
                actor=build_actor(permissions=[PermissionCode.REQUESTS_MANAGE.value]),
                request_id=student_request.id,
                payload=RequestApproveRequest(),
            )
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.message == "Solicitud no aprobable"


def test_cannot_approve_rejected_request() -> None:
    student_request = build_request_response(
        uuid4(),
        requester_id=uuid4(),
        status=RequestStatus.REJECTED,
    )
    service = StudentRequestService(
        FakeStudentRequestRepository(requests=[student_request])
    )

    with pytest.raises(AppError) as exc_info:
        asyncio.run(
            service.approve_request(
                actor=build_actor(permissions=[PermissionCode.REQUESTS_MANAGE.value]),
                request_id=student_request.id,
                payload=RequestApproveRequest(),
            )
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.message == "Solicitud no aprobable"


def test_invalid_request_category_is_rejected() -> None:
    service = StudentRequestService(
        FakeStudentRequestRepository(category_exists=False)
    )

    with pytest.raises(AppError) as exc_info:
        asyncio.run(
            service.create_request(
                actor=build_actor(),
                payload=RequestCreateRequest(
                    title="Solicitud",
                    description="Descripcion",
                    category_id=uuid4(),
                ),
            )
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.message == "Categoria invalida"


def test_comments_are_limited_to_owner_or_admin() -> None:
    owner_id = uuid4()
    internal_comment = build_comment_response(
        uuid4(),
        request_id=uuid4(),
        author_id=uuid4(),
        is_internal=True,
    )
    student_request = build_request_response(
        internal_comment.request_id,
        requester_id=owner_id,
        comments=[internal_comment],
    )
    repository = FakeStudentRequestRepository(requests=[student_request])
    service = StudentRequestService(repository)

    owner_view = asyncio.run(
        service.get_request(actor=build_actor(user_id=owner_id), request_id=student_request.id)
    )
    admin_comment = asyncio.run(
        service.create_comment(
            actor=build_actor(permissions=[PermissionCode.REQUESTS_MANAGE.value]),
            request_id=student_request.id,
            payload=RequestCommentCreateRequest(body="Revision interna", is_internal=True),
        )
    )

    with pytest.raises(AppError):
        asyncio.run(
            service.create_comment(
                actor=build_actor(user_id=uuid4()),
                request_id=student_request.id,
                payload=RequestCommentCreateRequest(body="No corresponde"),
            )
        )

    assert owner_view.comments == []
    assert admin_comment.is_internal is True


def test_owner_can_create_comment_via_route() -> None:
    owner_id = uuid4()
    student_request = build_request_response(uuid4(), requester_id=owner_id)
    service = StudentRequestService(
        FakeStudentRequestRepository(requests=[student_request])
    )
    client, token, _ = build_client(service, user_id=owner_id)

    response = client.post(
        f"/api/v1/requests/{student_request.id}/comments",
        headers=auth_header(token),
        json={"body": "Agrego antecedentes"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Comentario registrado"
    assert payload["data"]["body"] == "Agrego antecedentes"
    assert payload["data"]["is_internal"] is False


def test_non_owner_cannot_create_comment_via_route() -> None:
    student_request = build_request_response(uuid4(), requester_id=uuid4())
    service = StudentRequestService(
        FakeStudentRequestRepository(requests=[student_request])
    )
    client, token, _ = build_client(service, user_id=uuid4())

    response = client.post(
        f"/api/v1/requests/{student_request.id}/comments",
        headers=auth_header(token),
        json={"body": "No corresponde"},
    )

    assert response.status_code == 404
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Solicitud no encontrada"


def test_owner_cannot_create_internal_comment() -> None:
    owner_id = uuid4()
    student_request = build_request_response(uuid4(), requester_id=owner_id)
    service = StudentRequestService(
        FakeStudentRequestRepository(requests=[student_request])
    )
    client, token, _ = build_client(service, user_id=owner_id)

    response = client.post(
        f"/api/v1/requests/{student_request.id}/comments",
        headers=auth_header(token),
        json={"body": "Privado", "is_internal": True},
    )

    assert response.status_code == 403
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["message"] == "Permisos insuficientes"


def test_admin_can_view_internal_comments() -> None:
    internal_comment = build_comment_response(
        uuid4(),
        request_id=uuid4(),
        author_id=uuid4(),
        is_internal=True,
    )
    student_request = build_request_response(
        internal_comment.request_id,
        requester_id=uuid4(),
        comments=[internal_comment],
    )
    service = StudentRequestService(
        FakeStudentRequestRepository(requests=[student_request])
    )
    client, token, _ = build_client(
        service,
        permissions=[PermissionCode.REQUESTS_MANAGE.value],
    )

    response = client.get(
        f"/api/v1/requests/{student_request.id}",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert_standard_response_shape(payload)
    assert payload["data"]["comments"][0]["is_internal"] is True
