"""Pull a table/sheet/query from an existing live DataSource into a new
(or refreshed) Dataset.

Intended to be invoked from a Celery task for anything beyond a trivial
table (see ``infrastructure.celery.tasks.dataset_sync``) — the use case
itself has no opinion about who calls it, which is what makes that
possible: it's just an async method with no framework/queue coupling.
"""

from __future__ import annotations

from uuid import UUID

from quantix_api.application.interfaces.audit_logger import AuditLogger
from quantix_api.application.interfaces.connector_factory import ConnectorFactory
from quantix_api.application.interfaces.credential_cipher import CredentialCipher
from quantix_api.application.interfaces.dataset_storage import DatasetStorage
from quantix_api.application.use_cases._ingestion import ingest_into_dataset
from quantix_api.domain.entities.audit_log import AuditAction
from quantix_api.domain.entities.dataset import Dataset
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.domain.repositories.data_source_repository import DataSourceRepository
from quantix_api.domain.repositories.dataset_repository import DatasetRepository


class SyncDatasetUseCase:
    def __init__(
        self,
        *,
        data_source_repo: DataSourceRepository,
        dataset_repo: DatasetRepository,
        dataset_storage: DatasetStorage,
        connector_factory: ConnectorFactory,
        cipher: CredentialCipher,
        audit_logger: AuditLogger,
    ) -> None:
        self._data_source_repo = data_source_repo
        self._dataset_repo = dataset_repo
        self._dataset_storage = dataset_storage
        self._connector_factory = connector_factory
        self._cipher = cipher
        self._audit_logger = audit_logger

    async def create_pending(
        self,
        *,
        tenant_id: UUID,
        data_source_id: UUID,
        table_identifier: str,
        dataset_name: str | None,
    ) -> Dataset:
        """Create the (PENDING) dataset row without running ingestion —
        used by the async path, where a Celery task does the actual pull
        against a dataset ID the caller already has.
        """
        data_source = await self._data_source_repo.get_by_id(data_source_id)
        if data_source is None or data_source.tenant_id != tenant_id:
            raise EntityNotFoundError("DataSource", data_source_id)

        dataset = Dataset(
            tenant_id=tenant_id,
            data_source_id=data_source.id,
            name=dataset_name or table_identifier,
            table_identifier=table_identifier,
        )
        return await self._dataset_repo.add(dataset)

    async def execute(
        self,
        *,
        tenant_id: UUID,
        data_source_id: UUID,
        table_identifier: str,
        dataset_name: str | None,
        actor_user_id: UUID,
    ) -> Dataset:
        """Create a brand-new dataset pulled from an existing data source,
        ingesting inline (synchronous end-to-end — see ``create_pending``
        + ``resync`` for the async/Celery path).
        """
        dataset = await self.create_pending(
            tenant_id=tenant_id,
            data_source_id=data_source_id,
            table_identifier=table_identifier,
            dataset_name=dataset_name,
        )
        return await self._run(dataset=dataset, actor_user_id=actor_user_id)

    async def resync(self, *, tenant_id: UUID, dataset_id: UUID, actor_user_id: UUID) -> Dataset:
        """Re-pull the latest data for an already-existing dataset."""
        dataset = await self._dataset_repo.get_by_id(dataset_id)
        if dataset is None or dataset.tenant_id != tenant_id:
            raise EntityNotFoundError("Dataset", dataset_id)

        return await self._run(dataset=dataset, actor_user_id=actor_user_id)

    async def _run(self, *, dataset: Dataset, actor_user_id: UUID) -> Dataset:
        data_source = await self._data_source_repo.get_by_id(dataset.data_source_id)
        if data_source is None:
            raise EntityNotFoundError("DataSource", dataset.data_source_id)

        secrets = (
            self._cipher.decrypt(data_source.encrypted_secrets)
            if data_source.encrypted_secrets
            else {}
        )
        connector = self._connector_factory.build(data_source=data_source, secrets=secrets)

        dataset = await ingest_into_dataset(
            dataset=dataset,
            connector=connector,
            table_identifier=dataset.table_identifier,
            dataset_storage=self._dataset_storage,
            dataset_repo=self._dataset_repo,
        )

        await self._audit_logger.record(
            action=AuditAction.DATASET_INGESTED
            if dataset.status.value == "ready"
            else AuditAction.DATASET_INGESTION_FAILED,
            tenant_id=dataset.tenant_id,
            actor_user_id=actor_user_id,
            resource_type="dataset",
            resource_id=str(dataset.id),
            metadata={"table_identifier": dataset.table_identifier},
        )
        return dataset
