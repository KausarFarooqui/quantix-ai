"""Unit tests for SyncDatasetUseCase — covers the create_pending/execute
split (sync path) and resync (the path Celery's task drives), since a
prior bug had the async route double-creating datasets by calling
execute() *and* dispatching a Celery task with the same parameters.
"""

from __future__ import annotations

from uuid import uuid4

import pyarrow as pa
import pytest
from _connector_fakes import (
    FakeAuditLogger,
    FakeConnector,
    FakeConnectorFactory,
    FakeCredentialCipher,
    FakeDataSourceRepository,
    FakeDatasetRepository,
    FakeDatasetStorage,
)

from quantix_api.application.use_cases.sync_dataset import SyncDatasetUseCase
from quantix_api.domain.entities.data_source import DataSource, SourceType
from quantix_api.domain.entities.dataset import Dataset, DatasetStatus
from quantix_api.domain.exceptions.base import EntityNotFoundError


class TestSyncDatasetUseCase:
    def _build(self, connector: FakeConnector | None = None):
        data_source_repo = FakeDataSourceRepository()
        dataset_repo = FakeDatasetRepository()
        dataset_storage = FakeDatasetStorage()
        connector_factory = FakeConnectorFactory(connector)
        cipher = FakeCredentialCipher()
        audit_logger = FakeAuditLogger()
        use_case = SyncDatasetUseCase(
            data_source_repo=data_source_repo,
            dataset_repo=dataset_repo,
            dataset_storage=dataset_storage,
            connector_factory=connector_factory,
            cipher=cipher,
            audit_logger=audit_logger,
        )
        return use_case, data_source_repo, dataset_repo, audit_logger

    async def _seed_data_source(self, repo: FakeDataSourceRepository, tenant_id) -> DataSource:
        return await repo.add(
            DataSource(tenant_id=tenant_id, name="db", source_type=SourceType.SQLITE, config={})
        )

    async def test_create_pending_creates_a_pending_dataset_without_ingesting(self) -> None:
        use_case, data_source_repo, dataset_repo, _ = self._build(FakeConnector())
        tenant_id = uuid4()
        data_source = await self._seed_data_source(data_source_repo, tenant_id)

        dataset = await use_case.create_pending(
            tenant_id=tenant_id,
            data_source_id=data_source.id,
            table_identifier="orders",
            dataset_name=None,
        )

        assert dataset.status is DatasetStatus.PENDING
        assert dataset.row_count is None
        assert dataset.id in dataset_repo.store

    async def test_create_pending_unknown_data_source_raises(self) -> None:
        use_case, *_rest = self._build(FakeConnector())

        with pytest.raises(EntityNotFoundError):
            await use_case.create_pending(
                tenant_id=uuid4(), data_source_id=uuid4(), table_identifier="orders", dataset_name=None
            )

    async def test_execute_creates_and_ingests_in_one_call(self) -> None:
        table = pa.table({"id": [1, 2, 3]})
        use_case, data_source_repo, dataset_repo, audit_logger = self._build(FakeConnector(table=table))
        tenant_id = uuid4()
        data_source = await self._seed_data_source(data_source_repo, tenant_id)

        dataset = await use_case.execute(
            tenant_id=tenant_id,
            data_source_id=data_source.id,
            table_identifier="orders",
            dataset_name="Orders",
            actor_user_id=uuid4(),
        )

        assert dataset.status is DatasetStatus.READY
        assert dataset.row_count == 3
        # Exactly one dataset row should exist — execute() must not create
        # a second row on top of create_pending()'s row.
        assert len(dataset_repo.store) == 1
        assert any(r["action"].value == "dataset.ingested" for r in audit_logger.records)

    async def test_resync_reuses_the_existing_dataset_row(self) -> None:
        table = pa.table({"id": [1, 2]})
        use_case, data_source_repo, dataset_repo, _ = self._build(FakeConnector(table=table))
        tenant_id = uuid4()
        data_source = await self._seed_data_source(data_source_repo, tenant_id)
        existing = await dataset_repo.add(
            Dataset(
                tenant_id=tenant_id,
                data_source_id=data_source.id,
                name="Orders",
                table_identifier="orders",
            )
        )

        result = await use_case.resync(tenant_id=tenant_id, dataset_id=existing.id, actor_user_id=uuid4())

        assert result.id == existing.id
        assert result.status is DatasetStatus.READY
        assert result.row_count == 2
        assert len(dataset_repo.store) == 1

    async def test_resync_unknown_dataset_raises(self) -> None:
        use_case, *_rest = self._build(FakeConnector())

        with pytest.raises(EntityNotFoundError):
            await use_case.resync(tenant_id=uuid4(), dataset_id=uuid4(), actor_user_id=uuid4())

    async def test_resync_cross_tenant_raises(self) -> None:
        use_case, data_source_repo, dataset_repo, _ = self._build(FakeConnector())
        data_source = await self._seed_data_source(data_source_repo, uuid4())
        existing = await dataset_repo.add(
            Dataset(
                tenant_id=uuid4(),
                data_source_id=data_source.id,
                name="Orders",
                table_identifier="orders",
            )
        )

        with pytest.raises(EntityNotFoundError):
            await use_case.resync(tenant_id=uuid4(), dataset_id=existing.id, actor_user_id=uuid4())

    async def test_extraction_failure_marks_dataset_failed(self) -> None:
        use_case, data_source_repo, dataset_repo, audit_logger = self._build(
            FakeConnector(should_fail=True)
        )
        tenant_id = uuid4()
        data_source = await self._seed_data_source(data_source_repo, tenant_id)

        dataset = await use_case.execute(
            tenant_id=tenant_id,
            data_source_id=data_source.id,
            table_identifier="orders",
            dataset_name=None,
            actor_user_id=uuid4(),
        )

        assert dataset.status is DatasetStatus.FAILED
        assert dataset.status_message
        assert any(r["action"].value == "dataset.ingestion_failed" for r in audit_logger.records)
