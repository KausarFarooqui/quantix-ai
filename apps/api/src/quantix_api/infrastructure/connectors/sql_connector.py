"""Generic connector for every SQL-database source: PostgreSQL, MySQL,
SQL Server, SQLite, and Snowflake.

This is the payoff of the connector abstraction: five entries in the spec
("Support importing from... PostgreSQL, MySQL, SQL Server, SQLite,
Snowflake") become one class parametrized by dialect, because the actual
extraction logic — connect, inspect, run a query, get rows back — is
identical across all five once SQLAlchemy's dialect layer is doing the
translation. Adding a sixth SQL-based source (e.g. Redshift, another
Postgres-wire-compatible database) is a one-line addition to
``_DIALECT_DRIVERS``, not a new class.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

import pandas as pd
import pyarrow as pa
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine.reflection import Inspector

from quantix_api.application.interfaces.connector import ConnectionTestResult, TableSchema
from quantix_api.domain.entities.data_source import SourceType
from quantix_api.domain.entities.dataset import DatasetColumn, DatasetColumnType
from quantix_api.domain.exceptions.connectors import ExtractionError, SchemaDiscoveryError

# SQLAlchemy driver prefix per source type. Each requires the matching
# DBAPI package to be installed (see pyproject.toml): psycopg, pymysql,
# pymssql, sqlite3 (stdlib), snowflake-sqlalchemy.
_DIALECT_DRIVERS: dict[SourceType, str] = {
    SourceType.POSTGRESQL: "postgresql+psycopg",
    SourceType.MYSQL: "mysql+pymysql",
    SourceType.SQL_SERVER: "mssql+pymssql",
    SourceType.SQLITE: "sqlite",
}


class SqlDatabaseConnector:
    def __init__(self, *, source_type: SourceType, config: dict[str, Any], secrets: dict[str, Any]) -> None:
        self._source_type = source_type
        self._config = config
        self._secrets = secrets
        self._engine: Engine | None = None

    def test_connection(self) -> ConnectionTestResult:
        try:
            with self._get_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
            return ConnectionTestResult(success=True)
        except Exception as exc:  # noqa: BLE001 — any connectivity failure is a "test failed", not a crash
            return ConnectionTestResult(success=False, error=str(exc))

    def discover(self) -> list[TableSchema]:
        try:
            inspector: Inspector = inspect(self._get_engine())
            schema_name = self._config.get("schema")
            tables: list[TableSchema] = []
            for table_name in inspector.get_table_names(schema=schema_name):
                columns = [
                    DatasetColumn(
                        name=col["name"],
                        data_type=_sql_type_to_column_type(col["type"]),
                        nullable=bool(col.get("nullable", True)),
                    )
                    for col in inspector.get_columns(table_name, schema=schema_name)
                ]
                identifier = f"{schema_name}.{table_name}" if schema_name else table_name
                tables.append(TableSchema(identifier=identifier, columns=columns))
            return tables
        except Exception as exc:  # noqa: BLE001
            raise SchemaDiscoveryError(str(exc)) from exc

    def extract(self, table_identifier: str, *, limit: int | None = None) -> pa.Table:
        query = self._build_query(table_identifier, limit=limit)
        try:
            with self._get_engine().connect() as connection:
                dataframe = pd.read_sql(text(query), connection)
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(table_identifier, str(exc)) from exc
        return pa.Table.from_pandas(dataframe, preserve_index=False)

    @staticmethod
    def _build_query(table_identifier: str, *, limit: int | None) -> str:
        is_raw_query = table_identifier.strip().upper().startswith("SELECT")
        base = table_identifier if is_raw_query else f"SELECT * FROM {table_identifier}"
        if limit is None:
            return base
        if is_raw_query:
            return f"SELECT * FROM ({base}) AS quantix_subquery LIMIT {limit}"
        return f"{base} LIMIT {limit}"

    def _get_engine(self) -> Engine:
        if self._engine is None:
            self._engine = create_engine(self._build_url(), pool_pre_ping=True)
        return self._engine

    def _build_url(self) -> str:
        if self._source_type is SourceType.SNOWFLAKE:
            return self._build_snowflake_url()
        if self._source_type is SourceType.SQLITE:
            return f"sqlite:///{self._config['database']}"

        driver = _DIALECT_DRIVERS[self._source_type]
        user = quote_plus(self._secrets.get("username", ""))
        password = quote_plus(self._secrets.get("password", ""))
        host = self._config["host"]
        port = self._config.get("port")
        database = self._config.get("database", "")
        auth = f"{user}:{password}@" if user or password else ""
        host_port = f"{host}:{port}" if port else host
        return f"{driver}://{auth}{host_port}/{database}"

    def _build_snowflake_url(self) -> str:
        # Imported lazily: snowflake-sqlalchemy is a heavier optional
        # dependency that should only load when a Snowflake source is
        # actually configured.
        from snowflake.sqlalchemy import URL as snowflake_url

        return snowflake_url(
            account=self._config["account"],
            user=self._secrets.get("username", ""),
            password=self._secrets.get("password", ""),
            database=self._config.get("database"),
            schema=self._config.get("schema"),
            warehouse=self._config.get("warehouse"),
            role=self._config.get("role"),
        )


def _sql_type_to_column_type(sql_type: Any) -> DatasetColumnType:  # noqa: ANN401 — a SQLAlchemy TypeEngine instance, deliberately loosely typed across dialects
    type_name = type(sql_type).__name__.upper()
    if any(key in type_name for key in ("BOOL",)):
        return DatasetColumnType.BOOLEAN
    if any(key in type_name for key in ("INT", "SERIAL")):
        return DatasetColumnType.INTEGER
    if any(key in type_name for key in ("FLOAT", "REAL", "DOUBLE", "NUMERIC", "DECIMAL")):
        return DatasetColumnType.FLOAT
    if "TIMESTAMP" in type_name or "DATETIME" in type_name:
        return DatasetColumnType.DATETIME
    if type_name == "DATE":
        return DatasetColumnType.DATE
    if any(key in type_name for key in ("JSON",)):
        return DatasetColumnType.JSON
    return DatasetColumnType.STRING
