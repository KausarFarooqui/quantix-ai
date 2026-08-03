"""Unit tests for UploadFileDatasetUseCase — the file-upload ingestion
path, exercised end-to-end against fakes (no real DB/disk).
"""

from __future__ import annotations

from uuid import uuid4

import pyarrow as pa
from _connector_fakes import (
    FakeAuditLogger,
    FakeConnector,
    FakeConnectorFactory,
    FakeDataSourceRepository,
    FakeDatasetRepository,
    FakeDatasetStorage,
    FakeFileStorage,
)

from quantix_api.application.use_cases.upload_file_dataset import (
    UploadFileDatasetUseCase,
    infer_source_type,
)
from quantix_api.domain.entities.data_source import SourceType
from quantix_api.domain.entities.dataset import DatasetStatus
from quantix_api.domain.exceptions.connectors import UnsupportedFileFormatError

import pytest


class TestInferSourceType:
    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            ("sales.csv", SourceType.CSV),
            ("report.XLSX", SourceType.EXCEL),
            ("data.json", SourceType.JSON),
            ("export.parquet", SourceType.PARQUET),
        ],
    )
    def test_known_extensions(self, filename: str, expected: SourceType) -> None:
        assert infer_source_type(filename) == expected

    def test_unknown_extension_raises(self) -> None:
        with pytest.raises(UnsupportedFileFormatError):
            infer_source_type("archive.zip")


class TestUploadFileDatasetUseCase:
    def _build(self, connector: FakeConnector | None = None):
        data_source_repo = FakeDataSourceRepository()
        dataset_repo = FakeDatasetRepository()
        file_storage = FakeFileStorage()
        dataset_storage = FakeDatasetStorage()
        connector_factory = FakeConnectorFactory(connector)
        audit_logger = FakeAuditLogger()
        use_case = UploadFileDatasetUseCase(
            data_source_repo=data_source_repo,
            dataset_repo=dataset_repo,
            file_storage=file_storage,
            dataset_storage=dataset_storage,
            connector_factory=connector_factory,
            audit_logger=audit_logger,
        )
        return use_case, data_source_repo, dataset_repo, audit_logger

    async def test_successful_upload_creates_a_ready_dataset(self) -> None:
        table = pa.table({"id": [1, 2], "value": [10, 20]})
        use_case, data_source_repo, dataset_repo, audit_logger = self._build(
            FakeConnector(table=table)
        )

        dataset = await use_case.execute(
            tenant_id=uuid4(),
            actor_user_id=uuid4(),
            filename="sales.csv",
            content=b"id,value\n1,10\n2,20\n",
        )

        assert dataset.status is DatasetStatus.READY
        assert dataset.row_count == 2
        assert dataset.storage_uri is not None
        assert len(data_source_repo.store) == 1
        assert any(r["action"].value == "dataset.ingested" for r in audit_logger.records)

    async def test_extraction_failure_marks_dataset_failed_without_raising(self) -> None:
        use_case, *_rest, audit_logger = self._build(FakeConnector(should_fail=True))

        dataset = await use_case.execute(
            tenant_id=uuid4(),
            actor_user_id=uuid4(),
            filename="broken.csv",
            content=b"not,real,csv",
        )

        assert dataset.status is DatasetStatus.FAILED
        assert dataset.status_message
        assert any(r["action"].value == "dataset.ingestion_failed" for r in audit_logger.records)

    async def test_unsupported_extension_raises_before_touching_storage(self) -> None:
        use_case, data_source_repo, dataset_repo, _ = self._build()

        with pytest.raises(UnsupportedFileFormatError):
            await use_case.execute(
                tenant_id=uuid4(), actor_user_id=uuid4(), filename="archive.zip", content=b"junk"
            )

        assert data_source_repo.store == {}
        assert dataset_repo.store == {}
