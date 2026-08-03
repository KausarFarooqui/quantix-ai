"""Create a DataSource. Persists it as PENDING — callers typically follow
up with ``TestDataSourceConnectionUseCase`` for immediate feedback, kept
as a separate use case so creation and verification can be tested (and
can independently fail) on their own.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from quantix_api.application.interfaces.audit_logger import AuditLogger
from quantix_api.application.interfaces.credential_cipher import CredentialCipher
from quantix_api.domain.entities.audit_log import AuditAction
from quantix_api.domain.entities.data_source import DataSource, SourceType
from quantix_api.domain.repositories.data_source_repository import DataSourceRepository


class CreateDataSourceUseCase:
    def __init__(
        self,
        *,
        data_source_repo: DataSourceRepository,
        cipher: CredentialCipher,
        audit_logger: AuditLogger,
    ) -> None:
        self._data_source_repo = data_source_repo
        self._cipher = cipher
        self._audit_logger = audit_logger

    async def execute(
        self,
        *,
        tenant_id: UUID,
        name: str,
        source_type: SourceType,
        config: dict[str, Any],
        secrets: dict[str, Any] | None,
        created_by_user_id: UUID,
    ) -> DataSource:
        data_source = DataSource(
            tenant_id=tenant_id,
            name=name,
            source_type=source_type,
            config=config,
            encrypted_secrets=self._cipher.encrypt(secrets) if secrets else None,
            created_by_user_id=created_by_user_id,
        )
        data_source = await self._data_source_repo.add(data_source)

        await self._audit_logger.record(
            action=AuditAction.DATA_SOURCE_CREATED,
            tenant_id=tenant_id,
            actor_user_id=created_by_user_id,
            resource_type="data_source",
            resource_id=str(data_source.id),
            metadata={"source_type": source_type.value},
        )
        return data_source
