"""DuckDB/Parquet implementation of
``application.interfaces.dataset_storage.DatasetStorage``.

Every ingested dataset is materialized as a single Parquet file
(tenant- and dataset-scoped path). DuckDB reads Parquet natively and
efficiently — no separate load step, no long-running database process to
operate — which is why it's the analytics engine described in
ARCHITECTURE.md rather than a second copy of the data in Postgres.
"""

from __future__ import annotations

import re
from pathlib import Path
from uuid import UUID

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

# Deliberately conservative: only a bare SELECT (optionally wrapped in a
# CTE via WITH) is allowed through `query()`. This is a read-only preview
# tool for agents, not a general SQL execution endpoint — rejecting
# anything else here is cheaper and more legible than trying to sandbox
# DuckDB against DDL/attach/pragma statements downstream.
_ALLOWED_STATEMENT_PREFIX = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|copy|pragma|call|install|load)\b",
    re.IGNORECASE,
)


class DatasetQueryRejectedError(ValueError):
    """Raised when `query()` is given anything but a read-only SELECT."""


class DuckDBDatasetStorage:
    def __init__(self, *, base_dir: str) -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def write(self, *, tenant_id: UUID, dataset_id: UUID, table: pa.Table) -> tuple[str, int]:
        tenant_dir = self._base_dir / str(tenant_id)
        tenant_dir.mkdir(parents=True, exist_ok=True)
        path = tenant_dir / f"{dataset_id}.parquet"
        pq.write_table(table, path)
        return str(path), path.stat().st_size

    def read_preview(self, *, storage_uri: str, limit: int = 100) -> pa.Table:
        connection = duckdb.connect(database=":memory:")
        try:
            # `.fetch_arrow_table()` rather than `.arrow()`: depending on the
            # installed duckdb version, `.arrow()` can return a streaming
            # `RecordBatchReader` instead of a materialized `pa.Table`.
            # `.fetch_arrow_table()` is the explicit, version-stable way to
            # get a `pa.Table` back, which is what this method's return type
            # promises.
            return connection.execute(
                "SELECT * FROM read_parquet(?) LIMIT ?", [storage_uri, limit]
            ).fetch_arrow_table()
        finally:
            connection.close()

    def query(self, *, storage_uri: str, sql: str, limit: int = 1000) -> pa.Table:
        if not _ALLOWED_STATEMENT_PREFIX.match(sql) or _FORBIDDEN_KEYWORDS.search(sql):
            raise DatasetQueryRejectedError(
                "Only a single read-only SELECT statement is allowed"
            )
        if ";" in sql.rstrip().rstrip(";"):
            raise DatasetQueryRejectedError("Multiple statements are not allowed")

        connection = duckdb.connect(database=":memory:")
        try:
            connection.execute(
                "CREATE VIEW dataset AS SELECT * FROM read_parquet(?)", [storage_uri]
            )
            # Wrapping the caller's SQL in an outer LIMIT rather than
            # trusting it to include one keeps a runaway `SELECT *` from a
            # multi-million-row dataset from being fully materialized.
            wrapped = f"SELECT * FROM ({sql.rstrip().rstrip(';')}) AS _capped LIMIT ?"
            return connection.execute(wrapped, [limit]).fetch_arrow_table()
        finally:
            connection.close()

    def delete(self, *, storage_uri: str) -> None:
        path = Path(storage_uri)
        if path.exists():
            path.unlink()
