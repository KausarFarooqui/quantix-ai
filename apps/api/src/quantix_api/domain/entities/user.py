"""User domain entity and role-based access control primitives."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from quantix_api.domain.entities.base import TenantScopedEntity


class UserRole(StrEnum):
    """Coarse-grained RBAC role within a tenant.

    Fine-grained permissions (e.g. "can_export_report") are layered on top
    of roles in the authorization module rather than expanding this enum
    indefinitely.
    """

    OWNER = "owner"
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


_ROLE_RANK: dict[UserRole, int] = {
    UserRole.VIEWER: 0,
    UserRole.ANALYST: 1,
    UserRole.ADMIN: 2,
    UserRole.OWNER: 3,
}


@dataclass(kw_only=True, eq=False)  # see base.Entity docstring — required to inherit identity equality
class User(TenantScopedEntity):
    """A person who can authenticate into a tenant workspace."""

    email: str
    hashed_password: str | None  # None for OAuth-only accounts
    full_name: str
    role: UserRole = UserRole.VIEWER
    is_active: bool = True
    is_email_verified: bool = False

    def has_at_least(self, role: UserRole) -> bool:
        """Return True if this user's role meets or exceeds ``role``."""
        return _ROLE_RANK[self.role] >= _ROLE_RANK[role]
