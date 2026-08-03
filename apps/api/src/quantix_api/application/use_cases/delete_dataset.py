"""Delete a single Dataset and its materialized storage (the DataSource it
came from is left intact — deleting that is a separate, explicit action).
"""

from __future__ import annotations

from uuid import UUID

from quantix_api.application.interfaces.audit_logger import AuditLogger
from quantix_api.application.interfaces.dataset_storage import DatasetStorage
from quantix_api.domain.entities.audit_log import AuditAction
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.domain.repositories.dataset_repository import DatasetRepository


class DeleteDatasetUseCase:
    def __init__(
        self,
        *,
        dataset_repo: DatasetRepository,
        dataset_storage: DatasetStorage,
        audit_logger: AuditLogger,
    ) -> None:
        self._dataset_repo = dataset_repo
        self._dataset_storage = dataset_storage
        self._audit_logger = audit_logger

    async def execute(self, *, tenant_id: UUID, dataset_id: UUID, actor_user_id: UUID) -> None:
        dataset = await self._dataset_repo.get_by_id(dataset_id)
        if dataset is None or dataset.tenant_id != tenant_id:
            raise EntityNotFoundError("Dataset", dataset_id)

        if dataset.storage_uri:
            self._dataset_storage.delete(storage_uri=dataset.storage_uri)
        await self._dataset_repo.delete(dataset_id)

        await self._audit_logger.record(
            action=AuditAction.DATASET_DELETED,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            resource_type="dataset",
            resource_id=str(dataset_id),
        )
