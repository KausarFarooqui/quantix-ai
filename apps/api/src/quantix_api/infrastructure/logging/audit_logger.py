"""DB-backed implementation of ``application.interfaces.audit_logger.AuditLogger``.

Persists to the ``audit_logs`` table via the audit log repository. Also
mirrors every event into the structured application log (at INFO) so
audit events show up in log aggregation without a separate query against
Postgres — cheap, and useful for real-time alerting pipelines later.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from quantix_api.core.logging import get_logger
from quantix_api.domain.entities.audit_log import AuditAction, AuditLog
from quantix_api.domain.repositories.audit_log_repository import AuditLogRepository

logger = get_logger(__name__)


class DatabaseAuditLogger:
    def __init__(self, audit_log_repo: AuditLogRepository) -> None:
        self._audit_log_repo = audit_log_repo

    async def record(
        self,
        *,
        action: AuditAction,
        tenant_id: UUID | None,
        actor_user_id: UUID | None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        ip_address: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        entry = AuditLog(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            metadata_=metadata or {},
        )
        await self._audit_log_repo.add(entry)
        logger.info(
            "audit_event",
            action=action.value,
            tenant_id=str(tenant_id) if tenant_id else None,
            actor_user_id=str(actor_user_id) if actor_user_id else None,
            resource_type=resource_type,
            resource_id=resource_id,
        )
