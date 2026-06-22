from __future__ import annotations

from enum import StrEnum


class RoleCode(StrEnum):
    STUDENT = "STUDENT"
    BOARD_MEMBER = "BOARD_MEMBER"
    PRESIDENT = "PRESIDENT"
    TREASURER = "TREASURER"
    SECRETARY = "SECRETARY"
    ADMIN = "ADMIN"


class PermissionCode(StrEnum):
    USERS_MANAGE = "users.manage"
    ROLES_MANAGE = "roles.manage"
    CONTENT_PUBLISH = "content.publish"
    EVENTS_MANAGE = "events.manage"
    EVENTS_REGISTER = "events.register"
    REQUESTS_CREATE = "requests.create"
    REQUESTS_MANAGE = "requests.manage"
    DOCUMENTS_MANAGE = "documents.manage"
    FINANCES_MANAGE = "finances.manage"
    INVENTORY_MANAGE = "inventory.manage"
    MEETINGS_MANAGE = "meetings.manage"
    SURVEYS_MANAGE = "surveys.manage"
    VOTINGS_MANAGE = "votings.manage"
    AUDIT_VIEW = "audit.view"
    SYSTEM_ADMIN = "system.admin"


ADMINISTRATIVE_ROLES = {
    RoleCode.BOARD_MEMBER,
    RoleCode.PRESIDENT,
    RoleCode.TREASURER,
    RoleCode.SECRETARY,
    RoleCode.ADMIN,
}

ROLE_PRIORITY = [
    RoleCode.ADMIN,
    RoleCode.PRESIDENT,
    RoleCode.TREASURER,
    RoleCode.SECRETARY,
    RoleCode.BOARD_MEMBER,
    RoleCode.STUDENT,
]


def coerce_role(value: str) -> RoleCode | None:
    try:
        return RoleCode(value)
    except ValueError:
        return None


def normalize_roles(values: list[str] | tuple[str, ...]) -> list[RoleCode]:
    roles = [role for value in values if (role := coerce_role(str(value)))]
    return sorted(set(roles), key=ROLE_PRIORITY.index)


def select_primary_role(values: list[str] | tuple[str, ...]) -> RoleCode:
    roles = normalize_roles(values)
    return roles[0] if roles else RoleCode.STUDENT
