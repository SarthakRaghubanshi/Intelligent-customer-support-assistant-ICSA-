from typing import List, Union
from backend.models.user import UserRole

# Core Role-to-Permission Mappings
ROLE_PERMISSIONS = {
    UserRole.CUSTOMER.value: [
        "chat:read_write",
        "restaurant:view_menu"
    ],
    UserRole.RESTAURANT.value: [
        "chat:read_write",
        "restaurant:view_menu",
        "restaurant:write_profile",
        "analytics:read_own"
    ],
    UserRole.ADMIN.value: [
        "chat:read_write",
        "restaurant:view_menu",
        "restaurant:write_profile",
        "analytics:read_own",
        "analytics:read_all",
        "admin:manage_system"
    ]
}

def _normalize_role(role: Union[str, UserRole]) -> str:
    """Helper to convert UserRole enum to string value."""
    if isinstance(role, UserRole):
        return role.value
    return str(role).strip().lower()

def get_permissions(role: Union[str, UserRole]) -> List[str]:
    """
    Returns the list of permissions associated with the given role.
    """
    role_str = _normalize_role(role)
    return ROLE_PERMISSIONS.get(role_str, [])

def has_permission(role: Union[str, UserRole], permission: str) -> bool:
    """
    Checks if a role has a specific permission.
    """
    permissions = get_permissions(role)
    return permission in permissions

def has_role(user_role: Union[str, UserRole], target_role: Union[str, UserRole]) -> bool:
    """
    Checks if user_role matches the target_role.
    """
    user_role_str = _normalize_role(user_role)
    target_role_str = _normalize_role(target_role)
    return user_role_str == target_role_str
