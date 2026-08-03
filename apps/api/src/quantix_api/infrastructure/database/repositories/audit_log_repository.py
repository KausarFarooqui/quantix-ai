"""Concrete SQLAlchemy implementation of
``domain.repositories.audit_log_repository.AuditLogRepository``.
"""

from __future__ import annotations

from quantix_api.domain.entities.audit_log import AuditLog
from quantix_api.domain.repositories.audit_log_repository import AuditLogRepository
from quantix_api.infrastructure.database.models.audit_log import AuditLogModel
from quantix_api.infrastructure.database.repositories.sqlalchemy_repository import (
    SQLAlchemyRepository,
)


class SqlAlchemyAuditLogRepository(
    SQLAlchemyRepository[AuditLog, AuditLogModel], AuditLogRepository
):
    model = AuditLogModel

    def _to_entity(self, record: AuditLogModel) -> AuditLog:
        return AuditLog(
            id=record.id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            tenant_id=record.tenant_id,
            actor_user_id=record.actor_user_id,
            action=record.action,
            resource_type=record.resource_type,
            resource_id=record.resource_id,
            ip_address=record.ip_address,
            metadata_=record.event_metadata,
        )

    def _to_model(self, entity: AuditLog) -> AuditLogModel:
        return AuditLogModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            actor_user_id=entity.actor_user_id,
            action=entity.action,
            resource_type=entity.resource_type,
            resource_id=entity.resource_id,
            ip_address=entity.ip_address,
            event_metadata=entity.metadata_,
        )
