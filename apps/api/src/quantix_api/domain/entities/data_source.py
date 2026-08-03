"""DataSource domain entity — a stored, reusable "place data comes from."

Deliberately covers both live connections (PostgreSQL, Snowflake, ...) and
uploaded files under one concept: a file upload is modeled as a
``SourceType.CSV``/etc. DataSource whose ``config`` points at where the
raw file was stored, so the connector abstraction (see
``application.interfaces.connector``) has exactly one shape to satisfy
regardless of where the bytes ultimately come from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from quantix_api.domain.entities.base import TenantScopedEntity


class SourceType(StrEnum):
    """Every connector kind Quantix supports. Adding a new one is a
    two-step process: add the member here, and register a connector
    factory for it in ``infrastructure.connectors.registry``.
    """

    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"
    PARQUET = "parquet"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQL_SERVER = "sql_server"
    SQLITE = "sqlite"
    SNOWFLAKE = "snowflake"
    BIGQUERY = "bigquery"
    GOOGLE_SHEETS = "google_sheets"


FILE_SOURCE_TYPES = frozenset(
    {SourceType.CSV, SourceType.EXCEL, SourceType.JSON, SourceType.PARQUET}
)
DATABASE_SOURCE_TYPES = frozenset(
    {
        SourceType.POSTGRESQL,
        SourceType.MYSQL,
        SourceType.SQL_SERVER,
        SourceType.SQLITE,
        SourceType.SNOWFLAKE,
    }
)


class DataSourceStatus(StrEnum):
    PENDING = "pending"  # created, connection not yet tested
    ACTIVE = "active"  # last test_connection() succeeded
    ERROR = "error"  # last test_connection() failed


@dataclass(kw_only=True, eq=False)  # see base.Entity docstring — required to inherit identity equality
class DataSource(TenantScopedEntity):
    """A configured connection (or uploaded file) datasets can be pulled
    from. ``config`` holds non-secret connection parameters (host, port,
    database, project ID, spreadsheet ID, ...); anything sensitive lives
    encrypted in ``encrypted_secrets`` (see
    ``application.interfaces.credential_cipher``) and is never returned
    to the API.
    """

    name: str
    source_type: SourceType
    config: dict[str, Any] = field(default_factory=dict)
    encrypted_secrets: str | None = None
    status: DataSourceStatus = DataSourceStatus.PENDING
    last_tested_at: datetime | None = None
    last_test_error: str | None = None
    created_by_user_id: UUID | None = None

    @property
    def is_file_based(self) -> bool:
        return self.source_type in FILE_SOURCE_TYPES

    def mark_tested(self, *, success: bool, error: str | None = None) -> None:
        self.last_tested_at = datetime.now(UTC)
        self.status = DataSourceStatus.ACTIVE if success else DataSourceStatus.ERROR
        self.last_test_error = None if success else error
