"""Test connectivity for an existing DataSource and persist the outcome."""

from __future__ import annotations

from uuid import UUID

import anyio

from quantix_api.application.interfaces.audit_logger import AuditLogger
from quantix_api.application.interfaces.connector import ConnectionTestResult
from quantix_api.application.interfaces.connector_factory import ConnectorFactory
from quantix_api.application.interfaces.credential_cipher import CredentialCipher
from quantix_api.domain.entities.audit_log import AuditAction
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.domain.repositories.data_source_repository import DataSourceRepository


class TestDataSourceConnectionUseCase:
    def __init__(
        self,
        *,
        data_source_repo: DataSourceRepository,
        cipher: CredentialCipher,
        connector_factory: ConnectorFactory,
        audit_logger: AuditLogger,
    ) -> None:
        self._data_source_repo = data_source_repo
        self._cipher = cipher
        self._connector_factory = connector_factory
        self._audit_logger = audit_logger

    async def execute(
        self, *, tenant_id: UUID, data_source_id: UUID, actor_user_id: UUID
    ) -> ConnectionTestResult:
        data_source = await self._data_source_repo.get_by_id(data_source_id)
        if data_source is None or data_source.tenant_id != tenant_id:
            raise EntityNotFoundError("DataSource", data_source_id)

        secrets = self._cipher.decrypt(data_source.encrypted_secrets) if data_source.encrypted_secrets else {}
        connector = self._connector_factory.build(data_source=data_source, secrets=secrets)

        result = await anyio.to_thread.run_sync(connector.test_connection)

        data_source.mark_tested(success=result.success, error=result.error)
        await self._data_source_repo.update(data_source)

        await self._audit_logger.record(
            action=AuditAction.DATA_SOURCE_CONNECTION_TESTED,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            resource_type="data_source",
            resource_id=str(data_source.id),
            metadata={"success": result.success, "error": result.error},
        )
        return result
