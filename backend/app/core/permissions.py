from enum import Enum
from fastapi import Depends, HTTPException, status


class UserRole(str, Enum):
    PARTNER = "partner"
    FINANCE = "finance"
    ADMIN = "admin"


class Permission(str, Enum):
    APPROVE_TO_PAY = "approve_to_pay"
    REQUEST_APPROVAL = "request_approval"
    TOGGLE_PAID = "toggle_paid"
    TOGGLE_VAT_RECOVERED = "toggle_vat_recovered"
    EDIT_INVOICE = "edit_invoice"
    DELETE_INVOICE = "delete_invoice"
    MANAGE_MAPPINGS = "manage_mappings"
    MANAGE_USERS = "manage_users"
    SYSTEM_SETTINGS = "system_settings"


_BUSINESS_PERMS = {
    Permission.TOGGLE_PAID,
    Permission.TOGGLE_VAT_RECOVERED,
    Permission.EDIT_INVOICE,
    Permission.DELETE_INVOICE,
    Permission.MANAGE_MAPPINGS,
}

ROLE_PERMISSIONS = {
    UserRole.PARTNER.value: _BUSINESS_PERMS | {
        Permission.APPROVE_TO_PAY,
    },
    UserRole.FINANCE.value: _BUSINESS_PERMS | {
        Permission.REQUEST_APPROVAL,
    },
    UserRole.ADMIN.value: set(Permission),
}

def has_permission(user, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(user.role, set())


def user_permissions(user) -> list:
    return [p.value for p in ROLE_PERMISSIONS.get(user.role, set())]


def require_permission(permission: Permission):
    def _checker(user=Depends(_get_current_user())):
        if not has_permission(user, permission):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission.value}",
            )
        return user
    return _checker


def require_role(*allowed_roles: str):
    def _checker(user=Depends(_get_current_user())):
        if user.role not in allowed_roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {list(allowed_roles)}",
            )
        return user
    return _checker


def _get_current_user():
    from app.core.deps import current_user
    return current_user