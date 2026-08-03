"""Dataset domain entity — a materialized, queryable table ingested from a
DataSource (a specific database table/query, a spreadsheet tab, or the
whole of an uploaded file).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from quantix_api.domain.entities.base import TenantScopedEntity


class DatasetColumnType(StrEnum):
    """Normalized column type — every connector maps its native
    Arrow/DB-API type down to one of these so downstream consumers
    (profiling, SQL generation, charting) deal with one type system.
    """

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    JSON = "json"


@dataclass(frozen=True, slots=True)
class DatasetColumn:
    name: str
    data_type: DatasetColumnType
    nullable: bool = True


class DatasetStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


@dataclass(kw_only=True, eq=False)  # see base.Entity docstring — required to inherit identity equality
class Dataset(TenantScopedEntity):
    """A single ingested table. ``storage_uri`` points at the Parquet file
    (or DuckDB-queryable location) the data was materialized to —
    see ``application.interfaces.dataset_storage``.
    """

    data_source_id: UUID
    name: str
    table_identifier: str  # e.g. "public.orders", a sheet name, or the source filename
    schema: list[DatasetColumn] = field(default_factory=list)
    row_count: int | None = None
    size_bytes: int | None = None
    storage_uri: str | None = None
    status: DatasetStatus = DatasetStatus.PENDING
    status_message: str | None = None
    last_synced_at: datetime | None = None

    def mark_processing(self) -> None:
        self.status = DatasetStatus.PROCESSING
        self.status_message = None

    def mark_ready(
        self,
        *,
        schema: list[DatasetColumn],
        row_count: int,
        size_bytes: int,
        storage_uri: str,
    ) -> None:
        self.schema = schema
        self.row_count = row_count
        self.size_bytes = size_bytes
        self.storage_uri = storage_uri
        self.status = DatasetStatus.READY
        self.status_message = None
        self.last_synced_at = datetime.now(UTC)

    def mark_failed(self, message: str) -> None:
        self.status = DatasetStatus.FAILED
        self.status_message = message
