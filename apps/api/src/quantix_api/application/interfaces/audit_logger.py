"""Port for recording audit events — implemented by
``infrastructure.logging.audit_logger`` (persists to the ``audit_logs``
table).
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from quantix_api.domain.entities.audit_log import AuditAction


class AuditLogger(Protocol):
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
    ) -> None: ...
