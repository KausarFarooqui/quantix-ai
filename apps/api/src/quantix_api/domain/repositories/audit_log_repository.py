"""Abstract repository port for ``AuditLog`` entries.

Write-mostly: audit logs are append-only, so this port intentionally omits
``update``/``delete`` from the surface application code is expected to
use, even though the concrete repository still satisfies the base CRUD
contract for infrastructure-level cleanup/retention jobs.
"""

from __future__ import annotations

from abc import abstractmethod

from quantix_api.domain.entities.audit_log import AuditLog
from quantix_api.domain.repositories.base import AbstractRepository


class AuditLogRepository(AbstractRepository[AuditLog]):
    @abstractmethod
    async def add(self, entity: AuditLog) -> AuditLog:
        raise NotImplementedError  # pragma: no cover — abstract; the concrete repository overrides this
