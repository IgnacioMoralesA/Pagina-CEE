from __future__ import annotations

from fastapi import APIRouter, Depends

from app.backend.auth.dependencies import require_permissions
from app.backend.auth.permissions import PermissionCode
from app.backend.auth.schemas import UserPrincipal
from app.backend.core.responses import ApiResponse, success_response
from app.backend.users.dependencies import get_user_service
from app.backend.users.schemas import PermissionResponse, RoleResponse
from app.backend.users.service import UserService


router = APIRouter()


@router.get("/roles", response_model=ApiResponse[list[RoleResponse]])
async def list_roles(
    _: UserPrincipal = Depends(
        require_permissions(PermissionCode.ROLES_MANAGE.value)
    ),
    user_service: UserService = Depends(get_user_service),
) -> ApiResponse[list[RoleResponse]]:
    roles = await user_service.list_roles()
    return success_response(roles, "Roles obtenidos")


@router.get("/permissions", response_model=ApiResponse[list[PermissionResponse]])
async def list_permissions(
    _: UserPrincipal = Depends(
        require_permissions(PermissionCode.ROLES_MANAGE.value)
    ),
    user_service: UserService = Depends(get_user_service),
) -> ApiResponse[list[PermissionResponse]]:
    permissions = await user_service.list_permissions()
    return success_response(permissions, "Permisos obtenidos")
