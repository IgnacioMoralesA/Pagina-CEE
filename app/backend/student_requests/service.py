from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.audit.service import AuditService
from app.backend.auth.permissions import PermissionCode
from app.backend.auth.schemas import UserPrincipal
from app.backend.core.errors import AppError
from app.backend.core.responses import ErrorDetail
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


class StudentRequestRepository(Protocol):
    async def category_exists(self, category_id: UUID) -> bool:
        ...

    async def list_requests(
        self,
        *,
        requester_id: UUID | None,
        status: RequestStatus | None,
        category_id: UUID | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[StudentRequestResponse]:
        ...

    async def get_request(self, request_id: UUID) -> StudentRequestResponse | None:
        ...

    async def create_request(
        self,
        *,
        requester_id: UUID,
        payload: RequestCreateRequest,
    ) -> StudentRequestResponse:
        ...

    async def update_request(
        self,
        *,
        request_id: UUID,
        fields: dict[str, Any],
    ) -> StudentRequestResponse | None:
        ...

    async def add_status_history(
        self,
        *,
        request_id: UUID,
        old_status: RequestStatus | None,
        new_status: RequestStatus,
        changed_by: UUID,
        comment: str | None,
    ) -> RequestStatusHistoryResponse:
        ...

    async def add_comment(
        self,
        *,
        request_id: UUID,
        author_id: UUID,
        body: str,
        is_internal: bool,
    ) -> RequestCommentResponse:
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


class DatabaseStudentRequestRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def category_exists(self, category_id: UUID) -> bool:
        result = await self.db.execute(
            text(
                """
                SELECT 1
                FROM request_categories
                WHERE id = :category_id
                  AND is_active IS TRUE
                  AND deleted_at IS NULL
                """
            ),
            {"category_id": category_id},
        )
        return result.scalar_one_or_none() is not None

    async def list_requests(
        self,
        *,
        requester_id: UUID | None,
        status: RequestStatus | None,
        category_id: UUID | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[StudentRequestResponse]:
        where_sql, params = _request_where(
            requester_id=requester_id,
            status=status,
            category_id=category_id,
        )
        count_result = await self.db.execute(
            text(f"SELECT count(*) FROM requests r WHERE {where_sql}"),
            params,
        )
        result = await self.db.execute(
            text(
                f"""
                {_REQUEST_SELECT}
                WHERE {where_sql}
                ORDER BY r.created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {**params, "limit": limit, "offset": offset},
        )
        return PaginatedResponse[StudentRequestResponse](
            items=[_request_from_row(row) for row in result.mappings()],
            total=int(count_result.scalar_one()),
            limit=limit,
            offset=offset,
        )

    async def get_request(self, request_id: UUID) -> StudentRequestResponse | None:
        result = await self.db.execute(
            text(
                f"""
                {_REQUEST_SELECT}
                WHERE r.id = :request_id
                  AND r.deleted_at IS NULL
                """
            ),
            {"request_id": request_id},
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        student_request = _request_from_row(row)
        return student_request.model_copy(
            update={
                "status_history": await self._list_status_history(request_id),
                "comments": await self._list_comments(request_id),
            }
        )

    async def create_request(
        self,
        *,
        requester_id: UUID,
        payload: RequestCreateRequest,
    ) -> StudentRequestResponse:
        result = await self.db.execute(
            text(
                """
                INSERT INTO requests (
                    requester_id,
                    category_id,
                    title,
                    description,
                    status,
                    priority
                )
                VALUES (
                    :requester_id,
                    :category_id,
                    :title,
                    :description,
                    CAST(:status AS request_status),
                    CAST(:priority AS request_priority)
                )
                RETURNING id
                """
            ),
            {
                "requester_id": requester_id,
                "category_id": payload.category_id,
                "title": payload.title,
                "description": payload.description,
                "status": RequestStatus.SUBMITTED.value,
                "priority": payload.priority.value,
            },
        )
        request_id = UUID(str(result.scalar_one()))
        created = await self.get_request(request_id)
        if created is None:  # pragma: no cover - defensive guard.
            raise AppError(status_code=500, message="Error interno del servidor")
        return created

    async def update_request(
        self,
        *,
        request_id: UUID,
        fields: dict[str, Any],
    ) -> StudentRequestResponse | None:
        allowed_fields = {
            "title",
            "description",
            "category_id",
            "priority",
            "assigned_to",
            "resolution",
            "status",
            "resolved_at",
            "closed_at",
        }
        assignments = []
        params: dict[str, Any] = {"request_id": request_id}
        for field, value in fields.items():
            if field not in allowed_fields:
                continue
            if field == "status":
                assignments.append("status = CAST(:status AS request_status)")
                params[field] = _value(value)
            elif field == "priority":
                assignments.append("priority = CAST(:priority AS request_priority)")
                params[field] = _value(value)
            elif value is _SQL_NOW:
                assignments.append(f"{field} = now()")
            else:
                assignments.append(f"{field} = :{field}")
                params[field] = _value(value)

        if not assignments:
            return await self.get_request(request_id)

        assignments.append("updated_at = now()")
        result = await self.db.execute(
            text(
                f"""
                UPDATE requests
                SET {", ".join(assignments)}
                WHERE id = :request_id
                  AND deleted_at IS NULL
                RETURNING id
                """
            ),
            params,
        )
        if result.scalar_one_or_none() is None:
            return None
        return await self.get_request(request_id)

    async def add_status_history(
        self,
        *,
        request_id: UUID,
        old_status: RequestStatus | None,
        new_status: RequestStatus,
        changed_by: UUID,
        comment: str | None,
    ) -> RequestStatusHistoryResponse:
        result = await self.db.execute(
            text(
                """
                INSERT INTO request_status_history (
                    request_id,
                    old_status,
                    new_status,
                    changed_by,
                    comment
                )
                VALUES (
                    :request_id,
                    CAST(:old_status AS request_status),
                    CAST(:new_status AS request_status),
                    :changed_by,
                    :comment
                )
                RETURNING
                    id,
                    request_id,
                    old_status,
                    new_status,
                    changed_by,
                    comment,
                    created_at
                """
            ),
            {
                "request_id": request_id,
                "old_status": old_status.value if old_status is not None else None,
                "new_status": new_status.value,
                "changed_by": changed_by,
                "comment": comment,
            },
        )
        return _history_from_row(result.mappings().one())

    async def add_comment(
        self,
        *,
        request_id: UUID,
        author_id: UUID,
        body: str,
        is_internal: bool,
    ) -> RequestCommentResponse:
        result = await self.db.execute(
            text(
                """
                INSERT INTO request_comments (
                    request_id,
                    author_id,
                    body,
                    is_internal
                )
                VALUES (
                    :request_id,
                    :author_id,
                    :body,
                    :is_internal
                )
                RETURNING id
                """
            ),
            {
                "request_id": request_id,
                "author_id": author_id,
                "body": body,
                "is_internal": is_internal,
            },
        )
        comment_id = UUID(str(result.scalar_one()))
        comment = await self._get_comment_by_id(comment_id)
        if comment is None:  # pragma: no cover - defensive guard.
            raise AppError(status_code=500, message="Error interno del servidor")
        return comment

    async def commit(self) -> None:
        await self.db.commit()

    async def rollback(self) -> None:
        await self.db.rollback()

    async def _list_status_history(
        self,
        request_id: UUID,
    ) -> list[RequestStatusHistoryResponse]:
        result = await self.db.execute(
            text(
                """
                SELECT
                    id,
                    request_id,
                    old_status,
                    new_status,
                    changed_by,
                    comment,
                    created_at
                FROM request_status_history
                WHERE request_id = :request_id
                ORDER BY created_at ASC
                """
            ),
            {"request_id": request_id},
        )
        return [_history_from_row(row) for row in result.mappings()]

    async def _list_comments(self, request_id: UUID) -> list[RequestCommentResponse]:
        result = await self.db.execute(
            text(
                """
                SELECT
                    request_comments.id,
                    request_comments.request_id,
                    request_comments.author_id,
                    users.name AS author_name,
                    request_comments.body,
                    request_comments.is_internal,
                    request_comments.created_at,
                    request_comments.updated_at
                FROM request_comments
                JOIN users ON users.id = request_comments.author_id
                WHERE request_comments.request_id = :request_id
                  AND request_comments.deleted_at IS NULL
                ORDER BY request_comments.created_at ASC
                """
            ),
            {"request_id": request_id},
        )
        return [_comment_from_row(row) for row in result.mappings()]

    async def _get_comment_by_id(
        self,
        comment_id: UUID,
    ) -> RequestCommentResponse | None:
        result = await self.db.execute(
            text(
                """
                SELECT
                    request_comments.id,
                    request_comments.request_id,
                    request_comments.author_id,
                    users.name AS author_name,
                    request_comments.body,
                    request_comments.is_internal,
                    request_comments.created_at,
                    request_comments.updated_at
                FROM request_comments
                JOIN users ON users.id = request_comments.author_id
                WHERE request_comments.id = :comment_id
                  AND request_comments.deleted_at IS NULL
                """
            ),
            {"comment_id": comment_id},
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _comment_from_row(row)


class StudentRequestService:
    def __init__(
        self,
        repository: StudentRequestRepository,
        auditor: AdministrativeAuditor | None = None,
    ) -> None:
        self.repository = repository
        self.auditor = auditor

    async def list_requests(
        self,
        *,
        actor: UserPrincipal,
        scope: str | None,
        status: RequestStatus | None,
        category_id: UUID | None,
        limit: int,
        offset: int,
    ) -> PaginatedResponse[StudentRequestResponse]:
        is_admin = _has_manage_permission(actor)
        if scope == "all" and not is_admin:
            _raise_forbidden()
        if (status is not None or category_id is not None) and not is_admin:
            _raise_forbidden()

        requester_id = None if is_admin and scope != "mine" else actor.id
        return await self.repository.list_requests(
            requester_id=requester_id,
            status=status if is_admin else None,
            category_id=category_id if is_admin else None,
            limit=limit,
            offset=offset,
        )

    async def get_request(
        self,
        *,
        actor: UserPrincipal,
        request_id: UUID,
    ) -> StudentRequestResponse:
        student_request = await self._get_visible_request(
            actor=actor,
            request_id=request_id,
        )
        return _filter_visible_comments(student_request, _has_manage_permission(actor))

    async def create_request(
        self,
        *,
        actor: UserPrincipal,
        payload: RequestCreateRequest,
    ) -> StudentRequestResponse:
        await self._ensure_category_exists(payload.category_id)
        try:
            created = await self.repository.create_request(
                requester_id=actor.id,
                payload=payload,
            )
            await self.repository.add_status_history(
                request_id=created.id,
                old_status=None,
                new_status=RequestStatus.SUBMITTED,
                changed_by=actor.id,
                comment="Solicitud creada",
            )
            await self.repository.commit()
            refreshed = await self.repository.get_request(created.id)
            return refreshed or created
        except Exception:
            await self.repository.rollback()
            raise

    async def update_request(
        self,
        *,
        actor: UserPrincipal,
        request_id: UUID,
        payload: RequestUpdateRequest,
    ) -> StudentRequestResponse:
        existing = await self._get_visible_request(actor=actor, request_id=request_id)
        is_admin = _has_manage_permission(actor)
        fields = payload.model_dump(exclude_unset=True)
        _ensure_update_fields(fields)
        await self._ensure_category_exists(fields.get("category_id"))

        if not is_admin:
            if existing.requester_id != actor.id:
                raise AppError(status_code=404, message="Solicitud no encontrada")
            if existing.status not in {
                RequestStatus.SUBMITTED,
                RequestStatus.OBSERVED,
            }:
                raise AppError(
                    status_code=409,
                    message="Solicitud no editable",
                )
            forbidden_fields = {"assigned_to", "resolution"}
            if forbidden_fields.intersection(fields):
                _raise_forbidden()
        else:
            if existing.status == RequestStatus.CLOSED:
                raise AppError(status_code=409, message="Solicitud cerrada no editable")

        try:
            updated = await self.repository.update_request(
                request_id=request_id,
                fields=fields,
            )
            if updated is None:
                raise AppError(status_code=404, message="Solicitud no encontrada")
            if is_admin:
                await self._record_admin_action(
                    actor_id=actor.id,
                    request_id=request_id,
                    metadata={
                        "action": "request.updated",
                        "changed_fields": sorted(fields),
                    },
                )
            await self.repository.commit()
            return _filter_visible_comments(updated, is_admin)
        except Exception:
            await self.repository.rollback()
            raise

    async def assign_request(
        self,
        *,
        actor: UserPrincipal,
        request_id: UUID,
        payload: RequestAssignRequest,
    ) -> StudentRequestResponse:
        _ensure_manage_permission(actor)
        existing = await self._get_existing_request(request_id)
        _ensure_not_terminal_for_assignment(existing.status)

        fields: dict[str, Any] = {"assigned_to": payload.assigned_to}
        next_status = existing.status
        if existing.status in {RequestStatus.SUBMITTED, RequestStatus.OBSERVED}:
            next_status = RequestStatus.IN_REVIEW
            fields["status"] = next_status

        return await self._admin_update_with_optional_status_history(
            actor=actor,
            existing=existing,
            fields=fields,
            new_status=next_status if next_status != existing.status else None,
            history_comment=payload.comment or "Solicitud asignada",
            audit_action="request.assigned",
            metadata_extra={"assigned_to": str(payload.assigned_to)},
        )

    async def observe_request(
        self,
        *,
        actor: UserPrincipal,
        request_id: UUID,
        payload: RequestObserveRequest,
    ) -> StudentRequestResponse:
        _ensure_manage_permission(actor)
        existing = await self._get_existing_request(request_id)
        _ensure_transition_allowed(
            existing.status,
            forbidden={
                RequestStatus.APPROVED,
                RequestStatus.REJECTED,
                RequestStatus.CLOSED,
            },
            message="Solicitud no observable",
        )
        return await self._admin_update_with_optional_status_history(
            actor=actor,
            existing=existing,
            fields={"status": RequestStatus.OBSERVED},
            new_status=RequestStatus.OBSERVED,
            history_comment=payload.reason,
            audit_action="request.observed",
            metadata_extra={"reason": payload.reason},
        )

    async def approve_request(
        self,
        *,
        actor: UserPrincipal,
        request_id: UUID,
        payload: RequestApproveRequest,
    ) -> StudentRequestResponse:
        _ensure_manage_permission(actor)
        existing = await self._get_existing_request(request_id)
        _ensure_transition_allowed(
            existing.status,
            forbidden={RequestStatus.CLOSED, RequestStatus.REJECTED},
            message="Solicitud no aprobable",
        )
        return await self._admin_update_with_optional_status_history(
            actor=actor,
            existing=existing,
            fields={
                "status": RequestStatus.APPROVED,
                "resolution": payload.resolution,
                "resolved_at": _SQL_NOW,
            },
            new_status=RequestStatus.APPROVED,
            history_comment=payload.resolution or "Solicitud aprobada",
            audit_action="request.approved",
        )

    async def reject_request(
        self,
        *,
        actor: UserPrincipal,
        request_id: UUID,
        payload: RequestRejectRequest,
    ) -> StudentRequestResponse:
        _ensure_manage_permission(actor)
        existing = await self._get_existing_request(request_id)
        _ensure_transition_allowed(
            existing.status,
            forbidden={RequestStatus.CLOSED, RequestStatus.APPROVED},
            message="Solicitud no rechazable",
        )
        return await self._admin_update_with_optional_status_history(
            actor=actor,
            existing=existing,
            fields={
                "status": RequestStatus.REJECTED,
                "resolution": payload.reason,
                "resolved_at": _SQL_NOW,
            },
            new_status=RequestStatus.REJECTED,
            history_comment=payload.reason,
            audit_action="request.rejected",
            metadata_extra={"reason": payload.reason},
        )

    async def close_request(
        self,
        *,
        actor: UserPrincipal,
        request_id: UUID,
        payload: RequestCloseRequest,
    ) -> StudentRequestResponse:
        _ensure_manage_permission(actor)
        existing = await self._get_existing_request(request_id)
        _ensure_transition_allowed(
            existing.status,
            forbidden={RequestStatus.CLOSED},
            message="Solicitud ya cerrada",
        )
        return await self._admin_update_with_optional_status_history(
            actor=actor,
            existing=existing,
            fields={
                "status": RequestStatus.CLOSED,
                "closed_at": _SQL_NOW,
            },
            new_status=RequestStatus.CLOSED,
            history_comment=payload.comment or "Solicitud cerrada",
            audit_action="request.closed",
        )

    async def create_comment(
        self,
        *,
        actor: UserPrincipal,
        request_id: UUID,
        payload: RequestCommentCreateRequest,
    ) -> RequestCommentResponse:
        existing = await self._get_visible_request(actor=actor, request_id=request_id)
        is_admin = _has_manage_permission(actor)
        if payload.is_internal and not is_admin:
            _raise_forbidden()
        if existing.requester_id != actor.id and not is_admin:
            raise AppError(status_code=404, message="Solicitud no encontrada")

        try:
            comment = await self.repository.add_comment(
                request_id=request_id,
                author_id=actor.id,
                body=payload.body,
                is_internal=payload.is_internal,
            )
            await self.repository.commit()
            return comment
        except Exception:
            await self.repository.rollback()
            raise

    async def _admin_update_with_optional_status_history(
        self,
        *,
        actor: UserPrincipal,
        existing: StudentRequestResponse,
        fields: dict[str, Any],
        new_status: RequestStatus | None,
        history_comment: str,
        audit_action: str,
        metadata_extra: dict[str, object] | None = None,
    ) -> StudentRequestResponse:
        try:
            db_fields = {
                key: value
                for key, value in fields.items()
                if value is not None or key in {"resolution", "assigned_to"}
            }
            updated = await self.repository.update_request(
                request_id=existing.id,
                fields=db_fields,
            )
            if updated is None:
                raise AppError(status_code=404, message="Solicitud no encontrada")

            if new_status is not None and new_status != existing.status:
                await self.repository.add_status_history(
                    request_id=existing.id,
                    old_status=existing.status,
                    new_status=new_status,
                    changed_by=actor.id,
                    comment=history_comment,
                )

            metadata: dict[str, object] = {
                "action": audit_action,
                "old_status": existing.status.value,
                "new_status": updated.status.value,
            }
            if metadata_extra is not None:
                metadata.update(metadata_extra)
            await self._record_admin_action(
                actor_id=actor.id,
                request_id=existing.id,
                metadata=metadata,
            )
            await self.repository.commit()
            refreshed = await self.repository.get_request(existing.id)
            return _filter_visible_comments(refreshed or updated, True)
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

    async def _get_existing_request(
        self,
        request_id: UUID,
    ) -> StudentRequestResponse:
        student_request = await self.repository.get_request(request_id)
        if student_request is None:
            raise AppError(status_code=404, message="Solicitud no encontrada")
        return student_request

    async def _get_visible_request(
        self,
        *,
        actor: UserPrincipal,
        request_id: UUID,
    ) -> StudentRequestResponse:
        student_request = await self._get_existing_request(request_id)
        if student_request.requester_id == actor.id or _has_manage_permission(actor):
            return student_request
        raise AppError(status_code=404, message="Solicitud no encontrada")

    async def _record_admin_action(
        self,
        *,
        actor_id: UUID,
        request_id: UUID,
        metadata: dict[str, object],
    ) -> None:
        if self.auditor is None:
            return
        await self.auditor.record_administrative_action(
            actor_id=actor_id,
            entity_type="requests",
            entity_id=request_id,
            metadata=metadata,
        )


def create_student_request_service(db: AsyncSession) -> StudentRequestService:
    return StudentRequestService(
        DatabaseStudentRequestRepository(db),
        AuditService(db),
    )


class _SqlNow:
    pass


_SQL_NOW = _SqlNow()


def _value(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if value is _SQL_NOW:
        return None
    return value


def _request_where(
    *,
    requester_id: UUID | None,
    status: RequestStatus | None,
    category_id: UUID | None,
) -> tuple[str, dict[str, Any]]:
    params: dict[str, Any] = {}
    conditions = ["r.deleted_at IS NULL"]
    if requester_id is not None:
        conditions.append("r.requester_id = :requester_id")
        params["requester_id"] = requester_id
    if status is not None:
        conditions.append("r.status = CAST(:status AS request_status)")
        params["status"] = status.value
    if category_id is not None:
        conditions.append("r.category_id = :category_id")
        params["category_id"] = category_id
    return " AND ".join(conditions), params


def _has_manage_permission(actor: UserPrincipal) -> bool:
    return PermissionCode.REQUESTS_MANAGE.value in set(actor.permissions)


def _ensure_manage_permission(actor: UserPrincipal) -> None:
    if _has_manage_permission(actor):
        return
    _raise_forbidden()


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


def _ensure_transition_allowed(
    status: RequestStatus,
    *,
    forbidden: set[RequestStatus],
    message: str,
) -> None:
    if status not in forbidden:
        return
    raise AppError(status_code=409, message=message)


def _ensure_not_terminal_for_assignment(status: RequestStatus) -> None:
    if status not in {
        RequestStatus.CLOSED,
        RequestStatus.APPROVED,
        RequestStatus.REJECTED,
    }:
        return
    raise AppError(status_code=409, message="Solicitud no asignable")


def _filter_visible_comments(
    student_request: StudentRequestResponse,
    include_internal: bool,
) -> StudentRequestResponse:
    if include_internal:
        return student_request
    return student_request.model_copy(
        update={
            "comments": [
                comment
                for comment in student_request.comments
                if not comment.is_internal
            ]
        }
    )


def _normalize_status(value: object) -> RequestStatus:
    return RequestStatus(str(value).split(".")[-1].upper())


def _normalize_priority(value: object) -> RequestPriority:
    return RequestPriority(str(value).split(".")[-1].upper())


def _request_from_row(row: Any) -> StudentRequestResponse:
    return StudentRequestResponse(
        id=UUID(str(row["id"])),
        requester_id=UUID(str(row["requester_id"])),
        requester_name=row["requester_name"],
        category_id=UUID(str(row["category_id"])) if row["category_id"] else None,
        category_name=row["category_name"],
        category_slug=row["category_slug"],
        title=str(row["title"]),
        description=str(row["description"]),
        status=_normalize_status(row["status"]),
        priority=_normalize_priority(row["priority"]),
        assigned_to=UUID(str(row["assigned_to"])) if row["assigned_to"] else None,
        assigned_to_name=row["assigned_to_name"],
        resolution=row["resolution"],
        resolved_at=row["resolved_at"],
        closed_at=row["closed_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _history_from_row(row: Any) -> RequestStatusHistoryResponse:
    return RequestStatusHistoryResponse(
        id=UUID(str(row["id"])),
        request_id=UUID(str(row["request_id"])),
        old_status=_normalize_status(row["old_status"]) if row["old_status"] else None,
        new_status=_normalize_status(row["new_status"]),
        changed_by=UUID(str(row["changed_by"])) if row["changed_by"] else None,
        comment=row["comment"],
        created_at=row["created_at"],
    )


def _comment_from_row(row: Any) -> RequestCommentResponse:
    return RequestCommentResponse(
        id=UUID(str(row["id"])),
        request_id=UUID(str(row["request_id"])),
        author_id=UUID(str(row["author_id"])),
        author_name=row["author_name"],
        body=str(row["body"]),
        is_internal=bool(row["is_internal"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


_REQUEST_SELECT = """
SELECT
    r.id,
    r.requester_id,
    requester.name AS requester_name,
    r.category_id,
    c.name AS category_name,
    c.slug AS category_slug,
    r.title,
    r.description,
    r.status,
    r.priority,
    r.assigned_to,
    assignee.name AS assigned_to_name,
    r.resolution,
    r.resolved_at,
    r.closed_at,
    r.created_at,
    r.updated_at
FROM requests r
JOIN users requester ON requester.id = r.requester_id
LEFT JOIN request_categories c ON c.id = r.category_id
LEFT JOIN users assignee ON assignee.id = r.assigned_to
"""
