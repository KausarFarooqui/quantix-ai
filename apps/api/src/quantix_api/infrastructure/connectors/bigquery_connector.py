"""Connector for Google BigQuery.

Uses the native ``google-cloud-bigquery`` client rather than the
SQLAlchemy generic connector — BigQuery's query semantics (jobs, slots,
result pagination) don't map cleanly onto the DBAPI model the other SQL
sources share, and the native client's ``.to_arrow()`` gives a direct
Arrow result without a pandas round-trip.
"""

from __future__ import annotations

import json
from typing import Any

import pyarrow as pa

from quantix_api.application.interfaces.connector import ConnectionTestResult, TableSchema
from quantix_api.domain.entities.dataset import DatasetColumn, DatasetColumnType
from quantix_api.domain.exceptions.connectors import ExtractionError, SchemaDiscoveryError

_BQ_TYPE_MAP: dict[str, DatasetColumnType] = {
    "BOOLEAN": DatasetColumnType.BOOLEAN,
    "BOOL": DatasetColumnType.BOOLEAN,
    "INTEGER": DatasetColumnType.INTEGER,
    "INT64": DatasetColumnType.INTEGER,
    "FLOAT": DatasetColumnType.FLOAT,
    "FLOAT64": DatasetColumnType.FLOAT,
    "NUMERIC": DatasetColumnType.FLOAT,
    "BIGNUMERIC": DatasetColumnType.FLOAT,
    "TIMESTAMP": DatasetColumnType.DATETIME,
    "DATETIME": DatasetColumnType.DATETIME,
    "DATE": DatasetColumnType.DATE,
    "RECORD": DatasetColumnType.JSON,
    "STRUCT": DatasetColumnType.JSON,
}


class BigQueryConnector:
    def __init__(self, *, config: dict[str, Any], secrets: dict[str, Any]) -> None:
        self._project_id = config["project_id"]
        self._dataset = config.get("dataset")
        self._service_account_json = secrets.get("service_account_json")

    def _client(self):  # noqa: ANN202 — google.cloud.bigquery.Client, imported lazily below
        from google.cloud import bigquery

        if self._service_account_json:
            from google.oauth2 import service_account

            info = json.loads(self._service_account_json)
            credentials = service_account.Credentials.from_service_account_info(info)
            return bigquery.Client(project=self._project_id, credentials=credentials)
        # Falls back to Application Default Credentials (e.g. workload
        # identity in production) when no service-account JSON is supplied.
        return bigquery.Client(project=self._project_id)

    def test_connection(self) -> ConnectionTestResult:
        try:
            client = self._client()
            next(iter(client.list_datasets(max_results=1)), None)
            return ConnectionTestResult(success=True)
        except Exception as exc:  # noqa: BLE001
            return ConnectionTestResult(success=False, error=str(exc))

    def discover(self) -> list[TableSchema]:
        try:
            client = self._client()
            dataset_ref = f"{self._project_id}.{self._dataset}"
            schemas: list[TableSchema] = []
            for table_item in client.list_tables(dataset_ref):
                table = client.get_table(table_item.reference)
                columns = [
                    DatasetColumn(
                        name=field.name,
                        data_type=_BQ_TYPE_MAP.get(field.field_type, DatasetColumnType.STRING),
                        nullable=field.is_nullable,
                    )
                    for field in table.schema
                ]
                schemas.append(
                    TableSchema(
                        identifier=table_item.table_id,
                        columns=columns,
                        row_count_estimate=table.num_rows,
                    )
                )
            return schemas
        except Exception as exc:  # noqa: BLE001
            raise SchemaDiscoveryError(str(exc)) from exc

    def extract(self, table_identifier: str, *, limit: int | None = None) -> pa.Table:
        is_raw_query = table_identifier.strip().upper().startswith("SELECT")
        if is_raw_query:
            query = table_identifier
        else:
            query = f"SELECT * FROM `{self._project_id}.{self._dataset}.{table_identifier}`"
        if limit is not None:
            query = f"SELECT * FROM ({query}) AS quantix_subquery LIMIT {limit}" if is_raw_query else f"{query} LIMIT {limit}"

        try:
            client = self._client()
            return client.query(query).result().to_arrow()
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(table_identifier, str(exc)) from exc
