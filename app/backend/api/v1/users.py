from __future__ import annotations

from fastapi import APIRouter, Depends
from uuid import UUID

from app.backend.auth.dependencies import require_auth, require_permissions
from app.backend.auth.permissions import PermissionCode
from app.backend.auth.schemas import UserPrincipal
from app.backend.core.responses import ApiResponse, success_response
from app.backend.users.dependencies import get_user_service
from app.backend.users.schemas import (
    CurrentUserResponse,
    UserResponse,
    UserStatusUpdateRequest,
)
from app.backend.users.service import UserService, current_user_response_from_principal


router = APIRouter()


@router.get("/me", response_model=ApiResponse[CurrentUserResponse])
async def read_me(
    current_user: UserPrincipal = Depends(require_auth),
) -> ApiResponse[CurrentUserResponse]:
    user = current_user_response_from_principal(current_user)
    return success_response(user, "Usuario autenticado")


@router.get("", response_model=ApiResponse[list[UserResponse]])
async def list_users(
    _: UserPrincipal = Depends(
        require_permissions(PermissionCode.USERS_MANAGE.value)
    ),
    user_service: UserService = Depends(get_user_service),
) -> ApiResponse[list[UserResponse]]:
    users = await user_service.list_users()
    return success_response(users, "Usuarios obtenidos")


@router.get("/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user(
    user_id: UUID,
    _: UserPrincipal = Depends(
        require_permissions(PermissionCode.USERS_MANAGE.value)
    ),
    user_service: UserService = Depends(get_user_service),
) -> ApiResponse[UserResponse]:
    user = await user_service.get_user(user_id)
    return success_response(user, "Usuario obtenido")


@router.patch("/{user_id}/status", response_model=ApiResponse[UserResponse])
async def update_user_status(
    user_id: UUID,
    payload: UserStatusUpdateRequest,
    current_user: UserPrincipal = Depends(
        require_permissions(PermissionCode.USERS_MANAGE.value)
    ),
    user_service: UserService = Depends(get_user_service),
) -> ApiResponse[UserResponse]:
    user = await user_service.update_user_status(
        actor=current_user,
        user_id=user_id,
        status=payload.status,
    )
    return success_response(user, "Estado de usuario actualizado")
