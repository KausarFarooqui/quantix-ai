"""Read a small sample of a ready dataset back for a UI preview."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from quantix_api.application.interfaces.dataset_storage import DatasetStorage
from quantix_api.domain.entities.dataset import Dataset, DatasetStatus
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.domain.exceptions.connectors import DatasetNotReadyError
from quantix_api.domain.repositories.dataset_repository import DatasetRepository

MAX_PREVIEW_ROWS = 500
DEFAULT_PREVIEW_ROWS = 100


@dataclass(frozen=True, slots=True)
class DatasetPreview:
    dataset: Dataset
    rows: list[dict[str, Any]]


class GetDatasetPreviewUseCase:
    def __init__(self, *, dataset_repo: DatasetRepository, dataset_storage: DatasetStorage) -> None:
        self._dataset_repo = dataset_repo
        self._dataset_storage = dataset_storage

    async def execute(
        self, *, tenant_id: UUID, dataset_id: UUID, limit: int = DEFAULT_PREVIEW_ROWS
    ) -> DatasetPreview:
        dataset = await self._dataset_repo.get_by_id(dataset_id)
        if dataset is None or dataset.tenant_id != tenant_id:
            raise EntityNotFoundError("Dataset", dataset_id)

        if dataset.status is not DatasetStatus.READY or not dataset.storage_uri:
            raise DatasetNotReadyError(dataset_id, dataset.status.value)

        capped_limit = min(limit, MAX_PREVIEW_ROWS)
        table = self._dataset_storage.read_preview(storage_uri=dataset.storage_uri, limit=capped_limit)
        return DatasetPreview(dataset=dataset, rows=table.to_pylist())
