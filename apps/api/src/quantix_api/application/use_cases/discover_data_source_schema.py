"""List the tables/sheets available on a DataSource, with inferred
schemas — powers the "pick a table to import" step in the UI, before any
Dataset exists.
"""

from __future__ import annotations

from uuid import UUID

import anyio

from quantix_api.application.interfaces.connector import TableSchema
from quantix_api.application.interfaces.connector_factory import ConnectorFactory
from quantix_api.application.interfaces.credential_cipher import CredentialCipher
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.domain.repositories.data_source_repository import DataSourceRepository


class DiscoverDataSourceSchemaUseCase:
    def __init__(
        self,
        *,
        data_source_repo: DataSourceRepository,
        cipher: CredentialCipher,
        connector_factory: ConnectorFactory,
    ) -> None:
        self._data_source_repo = data_source_repo
        self._cipher = cipher
        self._connector_factory = connector_factory

    async def execute(self, *, tenant_id: UUID, data_source_id: UUID) -> list[TableSchema]:
        data_source = await self._data_source_repo.get_by_id(data_source_id)
        if data_source is None or data_source.tenant_id != tenant_id:
            raise EntityNotFoundError("DataSource", data_source_id)

        secrets = (
            self._cipher.decrypt(data_source.encrypted_secrets)
            if data_source.encrypted_secrets
            else {}
        )
        connector = self._connector_factory.build(data_source=data_source, secrets=secrets)
        return await anyio.to_thread.run_sync(connector.discover)
