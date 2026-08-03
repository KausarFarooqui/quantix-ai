"""Connector for Google Sheets, via the Sheets API v4 with service-account
credentials. Each sheet/tab within the spreadsheet is exposed as one
"table," matching how ``discover()`` treats a DB's tables.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import pyarrow as pa

from quantix_api.application.interfaces.connector import (
    ConnectionTestResult,
    TableSchema,
    arrow_type_to_column_type,
)
from quantix_api.domain.entities.dataset import DatasetColumn
from quantix_api.domain.exceptions.connectors import ExtractionError, SchemaDiscoveryError

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
DISCOVERY_SAMPLE_ROWS = 200


class GoogleSheetsConnector:
    def __init__(self, *, config: dict[str, Any], secrets: dict[str, Any]) -> None:
        self._spreadsheet_id = config["spreadsheet_id"]
        self._service_account_json = secrets.get("service_account_json")

    def _service(self):  # noqa: ANN202 — googleapiclient Resource, imported lazily below
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        info = json.loads(self._service_account_json)
        credentials = service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
        return build("sheets", "v4", credentials=credentials, cache_discovery=False)

    def test_connection(self) -> ConnectionTestResult:
        try:
            self._service().spreadsheets().get(spreadsheetId=self._spreadsheet_id).execute()
            return ConnectionTestResult(success=True)
        except Exception as exc:  # noqa: BLE001
            return ConnectionTestResult(success=False, error=str(exc))

    def discover(self) -> list[TableSchema]:
        try:
            metadata = self._service().spreadsheets().get(spreadsheetId=self._spreadsheet_id).execute()
            schemas: list[TableSchema] = []
            for sheet in metadata.get("sheets", []):
                title = sheet["properties"]["title"]
                table = self._read_sheet(title, limit=DISCOVERY_SAMPLE_ROWS)
                columns = [
                    DatasetColumn(
                        name=name, data_type=arrow_type_to_column_type(dtype), nullable=True
                    )
                    for name, dtype in zip(table.column_names, table.schema.types, strict=True)
                ]
                schemas.append(TableSchema(identifier=title, columns=columns))
            return schemas
        except Exception as exc:  # noqa: BLE001
            raise SchemaDiscoveryError(str(exc)) from exc

    def extract(self, table_identifier: str, *, limit: int | None = None) -> pa.Table:
        try:
            return self._read_sheet(table_identifier, limit=limit)
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(table_identifier, str(exc)) from exc

    def _read_sheet(self, sheet_name: str, *, limit: int | None) -> pa.Table:
        result = (
            self._service()
            .spreadsheets()
            .values()
            .get(spreadsheetId=self._spreadsheet_id, range=sheet_name)
            .execute()
        )
        values: list[list[str]] = result.get("values", [])
        if not values:
            return pa.table({})

        header, *rows = values
        if limit is not None:
            rows = rows[:limit]

        width = len(header)
        normalized_rows = [row + [None] * (width - len(row)) for row in rows]
        dataframe = pd.DataFrame(normalized_rows, columns=header)
        return pa.Table.from_pandas(dataframe, preserve_index=False)
