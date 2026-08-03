"""Connector for uploaded files — CSV, Excel, JSON, and Parquet.

One class, dispatching on ``SourceType`` internally, rather than four
near-identical classes: the only thing that differs between formats is
"how do I turn these bytes into a pyarrow.Table," which is a handful of
lines per format.
"""

from __future__ import annotations

import io
import json as json_module

import pandas as pd
import pyarrow as pa
import pyarrow.csv as pa_csv
import pyarrow.parquet as pa_parquet

from quantix_api.application.interfaces.connector import (
    ConnectionTestResult,
    TableSchema,
    arrow_type_to_column_type,
)
from quantix_api.application.interfaces.file_storage import FileStorage
from quantix_api.domain.entities.data_source import SourceType
from quantix_api.domain.entities.dataset import DatasetColumn
from quantix_api.domain.exceptions.connectors import ExtractionError, SchemaDiscoveryError

DISCOVERY_SAMPLE_ROWS = 1000


class FileConnector:
    def __init__(
        self,
        *,
        source_type: SourceType,
        file_storage: FileStorage,
        storage_path: str,
        filename: str,
    ) -> None:
        self._source_type = source_type
        self._file_storage = file_storage
        self._storage_path = storage_path
        self._filename = filename

    def test_connection(self) -> ConnectionTestResult:
        try:
            self._file_storage.read(storage_path=self._storage_path)
            return ConnectionTestResult(success=True)
        except OSError as exc:
            return ConnectionTestResult(success=False, error=str(exc))

    def discover(self) -> list[TableSchema]:
        try:
            table = self._parse(limit=DISCOVERY_SAMPLE_ROWS)
        except Exception as exc:  # noqa: BLE001 — normalize any parser error into a domain error
            raise SchemaDiscoveryError(str(exc)) from exc

        columns = [
            DatasetColumn(
                name=field.name,
                data_type=arrow_type_to_column_type(field.type),
                nullable=field.nullable,
            )
            for field in table.schema
        ]
        return [TableSchema(identifier=self._filename, columns=columns, row_count_estimate=None)]

    def extract(self, table_identifier: str, *, limit: int | None = None) -> pa.Table:
        try:
            return self._parse(limit=limit)
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(table_identifier, str(exc)) from exc

    def _parse(self, *, limit: int | None) -> pa.Table:
        content = self._file_storage.read(storage_path=self._storage_path)

        if self._source_type is SourceType.CSV:
            table = pa_csv.read_csv(io.BytesIO(content))
            return table.slice(0, limit) if limit is not None else table

        if self._source_type is SourceType.PARQUET:
            table = pa_parquet.read_table(io.BytesIO(content))
            return table.slice(0, limit) if limit is not None else table

        if self._source_type is SourceType.EXCEL:
            dataframe = pd.read_excel(io.BytesIO(content))
            if limit is not None:
                dataframe = dataframe.head(limit)
            return pa.Table.from_pandas(dataframe, preserve_index=False)

        if self._source_type is SourceType.JSON:
            dataframe = _read_json_flexibly(content)
            if limit is not None:
                dataframe = dataframe.head(limit)
            return pa.Table.from_pandas(dataframe, preserve_index=False)

        raise ValueError(f"FileConnector cannot handle source type {self._source_type!r}")


def _read_json_flexibly(content: bytes) -> pd.DataFrame:
    """Accept both a JSON array of objects and newline-delimited JSON —
    both are common "JSON export" shapes and there's no reliable way to
    tell which one a file is without trying.
    """
    text = content.decode("utf-8")
    try:
        parsed = json_module.loads(text)
        if isinstance(parsed, list):
            return pd.DataFrame(parsed)
        if isinstance(parsed, dict):
            return pd.DataFrame([parsed])
    except json_module.JSONDecodeError:
        pass
    return pd.read_json(io.StringIO(text), lines=True)
