"""ORM model for audit log entries."""

from __future__ import annotations

import uuid

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from quantix_api.domain.entities.audit_log import AuditAction
from quantix_api.infrastructure.database.models.base import (
    PORTABLE_JSON,
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class AuditLogModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    # Nullable + no ON DELETE CASCADE from tenants: audit history must
    # survive tenant deletion for compliance/forensics, so this is a
    # soft reference, not an FK constraint.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(index=True, nullable=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action", native_enum=True), nullable=False, index=True
    )
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6-safe length
    event_metadata: Mapped[dict] = mapped_column(PORTABLE_JSON, nullable=False, default=dict)
