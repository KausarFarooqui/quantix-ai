"""The connector port — the one interface every data source, live or
file-based, must satisfy. This is the extension point referenced
throughout the milestone: adding a new integration means implementing
this Protocol and registering it in
``infrastructure.connectors.registry``, nothing else in the application
or interface layers changes.

Note on layering: this module does a real (non-``TYPE_CHECKING``) import
of ``pyarrow``. That's a deliberate, narrow exception to "application
never imports third-party/infrastructure concerns" — Arrow tables are the
connector layer's lingua franca (every connector speaks Arrow in and out),
not an infrastructure detail being leaked upward. See ADR-0003.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import pyarrow as pa

from quantix_api.domain.entities.dataset import DatasetColumn, DatasetColumnType


@dataclass(frozen=True, slots=True)
class ConnectionTestResult:
    success: bool
    error: str | None = None


@dataclass(frozen=True, slots=True)
class TableSchema:
    """One extractable "table" as seen by a connector — a real DB table,
    a spreadsheet tab, or (for file connectors) the file itself.
    """

    identifier: str
    columns: list[DatasetColumn] = field(default_factory=list)
    row_count_estimate: int | None = None


class Connector(Protocol):
    """Implemented once per source type. All methods are synchronous and
    blocking by design — connectors do real network/disk I/O and are
    always invoked from use cases via a thread-offload (see
    ``application.use_cases._ingestion.ingest_into_dataset``), never
    directly on the event loop.
    """

    def test_connection(self) -> ConnectionTestResult:
        """Cheaply verify the source is reachable with the given config/secrets."""
        ...

    def discover(self) -> list[TableSchema]:
        """List the extractable tables/sheets and their inferred schemas."""
        ...

    def extract(self, table_identifier: str, *, limit: int | None = None) -> pa.Table:
        """Pull the given table's data as an Arrow table. ``limit`` caps
        row count for previews; omit for a full sync.
        """
        ...


def arrow_type_to_column_type(arrow_type: pa.DataType) -> DatasetColumnType:
    """Collapse pyarrow's many concrete types down to Quantix's small,
    normalized column-type vocabulary. Shared by every connector's
    ``discover()``/``extract()`` schema mapping and by the ingestion
    pipeline, so the normalization rule lives in exactly one place.
    """
    if pa.types.is_boolean(arrow_type):
        return DatasetColumnType.BOOLEAN
    if pa.types.is_integer(arrow_type):
        return DatasetColumnType.INTEGER
    if pa.types.is_floating(arrow_type) or pa.types.is_decimal(arrow_type):
        return DatasetColumnType.FLOAT
    if pa.types.is_timestamp(arrow_type):
        return DatasetColumnType.DATETIME
    if pa.types.is_date(arrow_type):
        return DatasetColumnType.DATE
    if pa.types.is_struct(arrow_type) or pa.types.is_list(arrow_type) or pa.types.is_map(arrow_type):
        return DatasetColumnType.JSON
    return DatasetColumnType.STRING
