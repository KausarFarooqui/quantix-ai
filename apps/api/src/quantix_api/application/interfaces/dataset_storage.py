"""Port for materializing an ingested Arrow table to durable, queryable
storage, and reading it back for previews.

The concrete implementation (``infrastructure.storage.duckdb_dataset_storage``)
writes Parquet and queries it with DuckDB, but nothing above this port
knows that — swapping the storage backend (e.g. to object storage +
a different query engine) touches one class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    import pyarrow as pa


class DatasetStorage(Protocol):
    def write(self, *, tenant_id: UUID, dataset_id: UUID, table: pa.Table) -> tuple[str, int]:
        """Persist ``table`` for this dataset. Returns (storage_uri, size_bytes)."""
        ...

    def read_preview(self, *, storage_uri: str, limit: int = 100) -> pa.Table:
        """Read up to ``limit`` rows back out for a UI preview."""
        ...

    def query(self, *, storage_uri: str, sql: str, limit: int = 1000) -> pa.Table:
        """Run a read-only SQL query against the materialized data (the
        table is addressed as ``dataset`` in ``sql``) — the primitive
        behind the SQL-generation agent's ``query_dataset`` tool
        (see ``infrastructure.agents.tools``). Implementations must reject
        anything but a single ``SELECT`` statement.
        """
        ...

    def delete(self, *, storage_uri: str) -> None:
        """Remove the materialized data. Idempotent — deleting an
        already-missing file is not an error.
        """
        ...
