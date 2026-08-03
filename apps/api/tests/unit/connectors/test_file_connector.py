"""Unit tests for FileConnector against real CSV/JSON/Parquet/Excel bytes."""

from __future__ import annotations

import io

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pa_parquet
from _connector_fakes import FakeFileStorage

from quantix_api.domain.entities.data_source import SourceType
from quantix_api.domain.entities.dataset import DatasetColumnType
from quantix_api.infrastructure.connectors.file_connector import FileConnector


def _make_connector(source_type: SourceType, content: bytes, filename: str) -> FileConnector:
    storage = FakeFileStorage()
    path = storage.save(tenant_id="tenant-1", filename=filename, content=content)  # type: ignore[arg-type]
    return FileConnector(source_type=source_type, file_storage=storage, storage_path=path, filename=filename)


class TestCsv:
    def _connector(self) -> FileConnector:
        content = b"id,name,active\n1,Alice,true\n2,Bob,false\n"
        return _make_connector(SourceType.CSV, content, "users.csv")

    def test_test_connection_succeeds(self) -> None:
        assert self._connector().test_connection().success is True

    def test_discover_infers_columns(self) -> None:
        tables = self._connector().discover()
        assert len(tables) == 1
        names = {c.name for c in tables[0].columns}
        assert names == {"id", "name", "active"}

    def test_extract_returns_all_rows(self) -> None:
        table = self._connector().extract("users.csv")
        assert table.num_rows == 2
        assert table.column("name").to_pylist() == ["Alice", "Bob"]

    def test_extract_respects_limit(self) -> None:
        table = self._connector().extract("users.csv", limit=1)
        assert table.num_rows == 1


class TestJson:
    def test_array_of_objects(self) -> None:
        content = b'[{"id": 1, "value": 10.5}, {"id": 2, "value": 20.5}]'
        connector = _make_connector(SourceType.JSON, content, "data.json")
        table = connector.extract("data.json")
        assert table.num_rows == 2
        assert table.column("value").to_pylist() == [10.5, 20.5]

    def test_newline_delimited(self) -> None:
        content = b'{"id": 1}\n{"id": 2}\n{"id": 3}\n'
        connector = _make_connector(SourceType.JSON, content, "data.ndjson")
        table = connector.extract("data.ndjson")
        assert table.num_rows == 3


class TestParquet:
    def test_roundtrip(self) -> None:
        original = pa.table({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        buffer = io.BytesIO()
        pa_parquet.write_table(original, buffer)
        connector = _make_connector(SourceType.PARQUET, buffer.getvalue(), "data.parquet")

        table = connector.extract("data.parquet")

        assert table.num_rows == 3
        assert table.column("a").to_pylist() == [1, 2, 3]


class TestExcel:
    def test_reads_first_sheet(self) -> None:
        dataframe = pd.DataFrame({"col_a": [1, 2], "col_b": ["x", "y"]})
        buffer = io.BytesIO()
        dataframe.to_excel(buffer, index=False)
        connector = _make_connector(SourceType.EXCEL, buffer.getvalue(), "data.xlsx")

        table = connector.extract("data.xlsx")

        assert table.num_rows == 2
        assert set(table.column_names) == {"col_a", "col_b"}


class TestArrowTypeMapping:
    def test_integer_and_string_columns_map_correctly(self) -> None:
        content = b"id,name\n1,Alice\n2,Bob\n"
        connector = _make_connector(SourceType.CSV, content, "users.csv")

        columns = {c.name: c.data_type for c in connector.discover()[0].columns}

        assert columns["id"] == DatasetColumnType.INTEGER
        assert columns["name"] == DatasetColumnType.STRING
