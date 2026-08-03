"""Tenant domain entity — the top-level isolation boundary in Quantix AI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from quantix_api.domain.entities.base import Entity


class TenantPlan(StrEnum):
    """Subscription tier — gates feature access and usage quotas."""

    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class TenantStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING_DELETION = "pending_deletion"


@dataclass(kw_only=True, eq=False)  # see base.Entity docstring — required to inherit identity equality
class Tenant(Entity):
    """An organization/workspace. All tenant-scoped data hangs off this."""

    name: str
    slug: str
    plan: TenantPlan = TenantPlan.FREE
    status: TenantStatus = TenantStatus.ACTIVE

    def suspend(self) -> None:
        self.status = TenantStatus.SUSPENDED

    def activate(self) -> None:
        self.status = TenantStatus.ACTIVE

    @property
    def is_active(self) -> bool:
        return self.status is TenantStatus.ACTIVE
