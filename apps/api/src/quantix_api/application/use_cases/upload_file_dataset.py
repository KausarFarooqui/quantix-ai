"""Upload a file (CSV/Excel/JSON/Parquet), infer its schema, and
materialize it as a ready-to-query Dataset — all in one request, since
file parsing is fast enough not to need Celery (unlike a live-source sync).

Creates a DataSource under the hood (see ADR-0003 for why file uploads are
modeled as a DataSource rather than a Dataset-only concept), so a re-parse
of the original bytes is always possible later without asking the user to
re-upload.
"""

from __future__ import annotations

from uuid import UUID

from quantix_api.application.interfaces.audit_logger import AuditLogger
from quantix_api.application.interfaces.connector_factory import ConnectorFactory
from quantix_api.application.interfaces.dataset_storage import DatasetStorage
from quantix_api.application.interfaces.file_storage import FileStorage
from quantix_api.application.use_cases._ingestion import ingest_into_dataset
from quantix_api.domain.entities.audit_log import AuditAction
from quantix_api.domain.entities.data_source import DataSource, DataSourceStatus, SourceType
from quantix_api.domain.entities.dataset import Dataset
from quantix_api.domain.exceptions.connectors import UnsupportedFileFormatError
from quantix_api.domain.repositories.data_source_repository import DataSourceRepository
from quantix_api.domain.repositories.dataset_repository import DatasetRepository

_EXTENSION_TO_SOURCE_TYPE: dict[str, SourceType] = {
    "csv": SourceType.CSV,
    "tsv": SourceType.CSV,
    "xlsx": SourceType.EXCEL,
    "xls": SourceType.EXCEL,
    "json": SourceType.JSON,
    "ndjson": SourceType.JSON,
    "parquet": SourceType.PARQUET,
}


def infer_source_type(filename: str) -> SourceType:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    try:
        return _EXTENSION_TO_SOURCE_TYPE[extension]
    except KeyError:
        raise UnsupportedFileFormatError(filename) from None


class UploadFileDatasetUseCase:
    def __init__(
        self,
        *,
        data_source_repo: DataSourceRepository,
        dataset_repo: DatasetRepository,
        file_storage: FileStorage,
        dataset_storage: DatasetStorage,
        connector_factory: ConnectorFactory,
        audit_logger: AuditLogger,
    ) -> None:
        self._data_source_repo = data_source_repo
        self._dataset_repo = dataset_repo
        self._file_storage = file_storage
        self._dataset_storage = dataset_storage
        self._connector_factory = connector_factory
        self._audit_logger = audit_logger

    async def execute(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        filename: str,
        content: bytes,
        dataset_name: str | None = None,
    ) -> Dataset:
        source_type = infer_source_type(filename)
        storage_path = self._file_storage.save(tenant_id=tenant_id, filename=filename, content=content)

        data_source = DataSource(
            tenant_id=tenant_id,
            name=filename,
            source_type=source_type,
            config={"original_filename": filename, "storage_path": storage_path},
            status=DataSourceStatus.ACTIVE,  # the file is right there — nothing to "test"
            created_by_user_id=actor_user_id,
        )
        data_source = await self._data_source_repo.add(data_source)

        dataset = Dataset(
            tenant_id=tenant_id,
            data_source_id=data_source.id,
            name=dataset_name or filename,
            table_identifier=filename,
        )
        dataset = await self._dataset_repo.add(dataset)

        connector = self._connector_factory.build(data_source=data_source, secrets={})
        dataset = await ingest_into_dataset(
            dataset=dataset,
            connector=connector,
            table_identifier=filename,
            dataset_storage=self._dataset_storage,
            dataset_repo=self._dataset_repo,
        )

        await self._audit_logger.record(
            action=AuditAction.DATASET_INGESTED
            if dataset.status.value == "ready"
            else AuditAction.DATASET_INGESTION_FAILED,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            resource_type="dataset",
            resource_id=str(dataset.id),
            metadata={"source_type": source_type.value, "filename": filename},
        )
        return dataset
