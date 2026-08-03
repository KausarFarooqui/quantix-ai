"""Unit tests for the DuckDB/Parquet dataset storage backend."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyarrow as pa

from quantix_api.infrastructure.storage.duckdb_dataset_storage import DuckDBDatasetStorage


class TestDuckDBDatasetStorage:
    def test_write_then_read_preview_roundtrips(self, tmp_path: Path) -> None:
        storage = DuckDBDatasetStorage(base_dir=str(tmp_path))
        table = pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        tenant_id, dataset_id = uuid4(), uuid4()

        storage_uri, size_bytes = storage.write(tenant_id=tenant_id, dataset_id=dataset_id, table=table)

        assert Path(storage_uri).exists()
        assert size_bytes > 0

        preview = storage.read_preview(storage_uri=storage_uri, limit=2)
        assert preview.num_rows == 2

    def test_delete_removes_the_file(self, tmp_path: Path) -> None:
        storage = DuckDBDatasetStorage(base_dir=str(tmp_path))
        table = pa.table({"id": [1]})
        storage_uri, _ = storage.write(tenant_id=uuid4(), dataset_id=uuid4(), table=table)

        storage.delete(storage_uri=storage_uri)

        assert not Path(storage_uri).exists()

    def test_delete_is_idempotent(self, tmp_path: Path) -> None:
        storage = DuckDBDatasetStorage(base_dir=str(tmp_path))
        # Deleting a path that was never written should not raise.
        storage.delete(storage_uri=str(tmp_path / "does-not-exist.parquet"))
