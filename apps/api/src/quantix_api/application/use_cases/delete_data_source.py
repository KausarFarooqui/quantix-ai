"""Delete a DataSource and every Dataset materialized from it, including
their off-database storage (raw uploaded file, Parquet output) — the
pieces a plain DB cascade wouldn't reach.
"""

from __future__ import annotations

from uuid import UUID

from quantix_api.application.interfaces.audit_logger import AuditLogger
from quantix_api.application.interfaces.dataset_storage import DatasetStorage
from quantix_api.application.interfaces.file_storage import FileStorage
from quantix_api.domain.entities.audit_log import AuditAction
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.domain.repositories.data_source_repository import DataSourceRepository
from quantix_api.domain.repositories.dataset_repository import DatasetRepository


class DeleteDataSourceUseCase:
    def __init__(
        self,
        *,
        data_source_repo: DataSourceRepository,
        dataset_repo: DatasetRepository,
        dataset_storage: DatasetStorage,
        file_storage: FileStorage,
        audit_logger: AuditLogger,
    ) -> None:
        self._data_source_repo = data_source_repo
        self._dataset_repo = dataset_repo
        self._dataset_storage = dataset_storage
        self._file_storage = file_storage
        self._audit_logger = audit_logger

    async def execute(self, *, tenant_id: UUID, data_source_id: UUID, actor_user_id: UUID) -> None:
        data_source = await self._data_source_repo.get_by_id(data_source_id)
        if data_source is None or data_source.tenant_id != tenant_id:
            raise EntityNotFoundError("DataSource", data_source_id)

        for dataset in await self._dataset_repo.list_for_data_source(data_source_id):
            if dataset.storage_uri:
                self._dataset_storage.delete(storage_uri=dataset.storage_uri)
            await self._dataset_repo.delete(dataset.id)

        if data_source.is_file_based:
            storage_path = data_source.config.get("storage_path")
            if storage_path:
                self._file_storage.delete(storage_path=storage_path)

        await self._data_source_repo.delete(data_source_id)

        await self._audit_logger.record(
            action=AuditAction.DATA_SOURCE_DELETED,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            resource_type="data_source",
            resource_id=str(data_source_id),
        )
