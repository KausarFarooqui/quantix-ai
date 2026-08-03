"""Shared ingestion helper: run a connector's extraction, materialize the
result, and update the dataset's status accordingly.

Used by both ``upload_file_dataset`` and ``sync_dataset`` — the only
difference between "upload a CSV" and "sync a Postgres table" is how the
``Connector`` and ``Dataset`` got constructed; what happens next is
identical.
"""

from __future__ import annotations

import anyio
import pyarrow as pa

from quantix_api.application.interfaces.connector import Connector, arrow_type_to_column_type
from quantix_api.application.interfaces.dataset_storage import DatasetStorage
from quantix_api.core.logging import get_logger
from quantix_api.domain.entities.dataset import Dataset, DatasetColumn
from quantix_api.domain.repositories.dataset_repository import DatasetRepository

logger = get_logger(__name__)


async def ingest_into_dataset(
    *,
    dataset: Dataset,
    connector: Connector,
    table_identifier: str,
    dataset_storage: DatasetStorage,
    dataset_repo: DatasetRepository,
    row_limit: int | None = None,
) -> Dataset:
    dataset.mark_processing()
    dataset = await dataset_repo.update(dataset)

    try:
        # Connector I/O is blocking (network/disk); offload to a worker
        # thread so it never stalls the event loop, whether this runs
        # inline from a request handler or inside a Celery task's own
        # asyncio.run() loop.
        table = await anyio.to_thread.run_sync(
            lambda: connector.extract(table_identifier, limit=row_limit)
        )
        schema = _arrow_schema_to_columns(table)
        storage_uri, size_bytes = dataset_storage.write(
            tenant_id=dataset.tenant_id, dataset_id=dataset.id, table=table
        )
    except Exception as exc:  # noqa: BLE001 — deliberately broad: any failure here is a dataset-level failure, not a request error
        logger.warning(
            "dataset_ingestion_failed",
            dataset_id=str(dataset.id),
            table_identifier=table_identifier,
            error=str(exc),
        )
        dataset.mark_failed(str(exc))
        return await dataset_repo.update(dataset)

    dataset.mark_ready(
        schema=schema, row_count=table.num_rows, size_bytes=size_bytes, storage_uri=storage_uri
    )
    return await dataset_repo.update(dataset)


def _arrow_schema_to_columns(table: pa.Table) -> list[DatasetColumn]:
    return [
        DatasetColumn(
            name=field.name,
            data_type=arrow_type_to_column_type(field.type),
            nullable=field.nullable,
        )
        for field in table.schema
    ]
