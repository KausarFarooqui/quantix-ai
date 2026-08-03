"""Unit tests for GetDatasetPreviewUseCase and DeleteDatasetUseCase."""

from __future__ import annotations

from uuid import uuid4

import pyarrow as pa
import pytest
from _connector_fakes import FakeAuditLogger, FakeDatasetRepository, FakeDatasetStorage

from quantix_api.application.use_cases.delete_dataset import DeleteDatasetUseCase
from quantix_api.application.use_cases.get_dataset_preview import (
    MAX_PREVIEW_ROWS,
    GetDatasetPreviewUseCase,
)
from quantix_api.domain.entities.dataset import Dataset, DatasetStatus
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.domain.exceptions.connectors import DatasetNotReadyError


class TestGetDatasetPreviewUseCase:
    def _build(self):
        dataset_repo = FakeDatasetRepository()
        dataset_storage = FakeDatasetStorage()
        use_case = GetDatasetPreviewUseCase(dataset_repo=dataset_repo, dataset_storage=dataset_storage)
        return use_case, dataset_repo, dataset_storage

    async def test_returns_rows_for_a_ready_dataset(self) -> None:
        use_case, dataset_repo, dataset_storage = self._build()
        tenant_id = uuid4()
        table = pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        storage_uri, size_bytes = dataset_storage.write(tenant_id=tenant_id, dataset_id=uuid4(), table=table)
        dataset = Dataset(
            tenant_id=tenant_id, data_source_id=uuid4(), name="orders", table_identifier="orders"
        )
        dataset.mark_ready(schema=[], row_count=3, size_bytes=size_bytes, storage_uri=storage_uri)
        dataset = await dataset_repo.add(dataset)

        preview = await use_case.execute(tenant_id=tenant_id, dataset_id=dataset.id)

        assert len(preview.rows) == 3
        assert preview.rows[0] == {"id": 1, "name": "a"}

    async def test_caps_limit_at_max_preview_rows(self) -> None:
        use_case, dataset_repo, dataset_storage = self._build()
        tenant_id = uuid4()
        table = pa.table({"id": list(range(1000))})
        storage_uri, size_bytes = dataset_storage.write(tenant_id=tenant_id, dataset_id=uuid4(), table=table)
        dataset = Dataset(
            tenant_id=tenant_id, data_source_id=uuid4(), name="big", table_identifier="big"
        )
        dataset.mark_ready(schema=[], row_count=1000, size_bytes=size_bytes, storage_uri=storage_uri)
        dataset = await dataset_repo.add(dataset)

        preview = await use_case.execute(tenant_id=tenant_id, dataset_id=dataset.id, limit=10_000)

        assert len(preview.rows) == MAX_PREVIEW_ROWS

    async def test_not_ready_dataset_raises(self) -> None:
        use_case, dataset_repo, _storage = self._build()
        tenant_id = uuid4()
        dataset = await dataset_repo.add(
            Dataset(tenant_id=tenant_id, data_source_id=uuid4(), name="orders", table_identifier="orders")
        )
        assert dataset.status is DatasetStatus.PENDING

        with pytest.raises(DatasetNotReadyError):
            await use_case.execute(tenant_id=tenant_id, dataset_id=dataset.id)

    async def test_unknown_dataset_raises_not_found(self) -> None:
        use_case, *_rest = self._build()

        with pytest.raises(EntityNotFoundError):
            await use_case.execute(tenant_id=uuid4(), dataset_id=uuid4())

    async def test_cross_tenant_access_raises_not_found(self) -> None:
        use_case, dataset_repo, _storage = self._build()
        dataset = await dataset_repo.add(
            Dataset(tenant_id=uuid4(), data_source_id=uuid4(), name="orders", table_identifier="orders")
        )

        with pytest.raises(EntityNotFoundError):
            await use_case.execute(tenant_id=uuid4(), dataset_id=dataset.id)


class TestDeleteDatasetUseCase:
    def _build(self):
        dataset_repo = FakeDatasetRepository()
        dataset_storage = FakeDatasetStorage()
        audit_logger = FakeAuditLogger()
        use_case = DeleteDatasetUseCase(
            dataset_repo=dataset_repo, dataset_storage=dataset_storage, audit_logger=audit_logger
        )
        return use_case, dataset_repo, dataset_storage, audit_logger

    async def test_removes_dataset_and_its_storage(self) -> None:
        use_case, dataset_repo, dataset_storage, audit_logger = self._build()
        tenant_id = uuid4()
        table = pa.table({"id": [1]})
        storage_uri, size_bytes = dataset_storage.write(tenant_id=tenant_id, dataset_id=uuid4(), table=table)
        dataset = Dataset(
            tenant_id=tenant_id, data_source_id=uuid4(), name="orders", table_identifier="orders"
        )
        dataset.mark_ready(schema=[], row_count=1, size_bytes=size_bytes, storage_uri=storage_uri)
        dataset = await dataset_repo.add(dataset)

        await use_case.execute(tenant_id=tenant_id, dataset_id=dataset.id, actor_user_id=uuid4())

        assert dataset.id not in dataset_repo.store
        assert storage_uri not in dataset_storage._tables  # noqa: SLF001
        assert any(r["action"].value == "dataset.deleted" for r in audit_logger.records)

    async def test_pending_dataset_with_no_storage_deletes_cleanly(self) -> None:
        use_case, dataset_repo, _storage, _audit = self._build()
        tenant_id = uuid4()
        dataset = await dataset_repo.add(
            Dataset(tenant_id=tenant_id, data_source_id=uuid4(), name="orders", table_identifier="orders")
        )

        await use_case.execute(tenant_id=tenant_id, dataset_id=dataset.id, actor_user_id=uuid4())

        assert dataset.id not in dataset_repo.store

    async def test_unknown_dataset_raises_not_found(self) -> None:
        use_case, *_rest = self._build()

        with pytest.raises(EntityNotFoundError):
            await use_case.execute(tenant_id=uuid4(), dataset_id=uuid4(), actor_user_id=uuid4())
