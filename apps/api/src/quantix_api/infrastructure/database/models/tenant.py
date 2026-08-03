"""ORM model for tenants."""

from __future__ import annotations

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from quantix_api.domain.entities.tenant import TenantPlan, TenantStatus
from quantix_api.infrastructure.database.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class TenantModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(63), nullable=False, unique=True, index=True)
    plan: Mapped[TenantPlan] = mapped_column(
        Enum(TenantPlan, name="tenant_plan", native_enum=True),
        nullable=False,
        default=TenantPlan.FREE,
    )
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenant_status", native_enum=True),
        nullable=False,
        default=TenantStatus.ACTIVE,
    )
