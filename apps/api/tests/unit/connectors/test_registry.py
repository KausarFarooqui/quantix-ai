"""Unit tests for ``ConnectorRegistry`` — verifies it dispatches each
``SourceType`` to the right concrete connector class without needing real
network/database credentials, since every connector's ``__init__`` only
stores its config (connections happen lazily inside ``test_connection``/
``discover``/``extract``, which these tests never call).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from _connector_fakes import FakeFileStorage
from quantix_api.domain.entities.data_source import DataSource, SourceType
from quantix_api.domain.exceptions.connectors import UnsupportedSourceTypeError
from quantix_api.infrastructure.connectors.bigquery_connector import BigQueryConnector
from quantix_api.infrastructure.connectors.file_connector import FileConnector
from quantix_api.infrastructure.connectors.google_sheets_connector import GoogleSheetsConnector
from quantix_api.infrastructure.connectors.registry import ConnectorRegistry
from quantix_api.infrastructure.connectors.sql_connector import SqlDatabaseConnector


def _data_source(*, source_type: SourceType, config: dict) -> DataSource:
    return DataSource(tenant_id=uuid4(), name="src", source_type=source_type, config=config)


class TestConnectorRegistry:
    def test_builds_file_connector_for_file_source_types(self) -> None:
        registry = ConnectorRegistry(file_storage=FakeFileStorage())
        data_source = _data_source(
            source_type=SourceType.CSV,
            config={"storage_path": "memory://tenant/1_orders.csv", "original_filename": "orders.csv"},
        )

        connector = registry.build(data_source=data_source, secrets={})

        assert isinstance(connector, FileConnector)

    def test_builds_sql_connector_for_database_source_types(self) -> None:
        registry = ConnectorRegistry(file_storage=FakeFileStorage())
        data_source = _data_source(
            source_type=SourceType.POSTGRESQL,
            config={"host": "localhost", "port": 5432, "database": "quantix", "username": "u"},
        )

        connector = registry.build(data_source=data_source, secrets={"password": "p"})

        assert isinstance(connector, SqlDatabaseConnector)

    def test_builds_bigquery_connector(self) -> None:
        registry = ConnectorRegistry(file_storage=FakeFileStorage())
        data_source = _data_source(
            source_type=SourceType.BIGQUERY, config={"project_id": "my-project", "dataset": "my_dataset"}
        )

        connector = registry.build(data_source=data_source, secrets={})

        assert isinstance(connector, BigQueryConnector)

    def test_builds_google_sheets_connector(self) -> None:
        registry = ConnectorRegistry(file_storage=FakeFileStorage())
        data_source = _data_source(
            source_type=SourceType.GOOGLE_SHEETS, config={"spreadsheet_id": "abc123"}
        )

        connector = registry.build(data_source=data_source, secrets={})

        assert isinstance(connector, GoogleSheetsConnector)

    def test_unsupported_source_type_raises(self) -> None:
        registry = ConnectorRegistry(file_storage=FakeFileStorage())
        data_source = _data_source(source_type=SourceType.SNOWFLAKE, config={})
        # SNOWFLAKE is a real, supported SourceType (routed through
        # SqlDatabaseConnector via DATABASE_SOURCE_TYPES) — to reach the
        # registry's fallback branch we need a source_type that's neither
        # file-, database-, BigQuery-, nor Sheets-shaped. There isn't one
        # left on the real enum, so this stands in for a future,
        # not-yet-wired-up SourceType member. It needs to be hashable (the
        # registry checks `in FILE_SOURCE_TYPES`/`DATABASE_SOURCE_TYPES`,
        # both frozensets) and expose `.value` (`UnsupportedSourceTypeError`
        # reads it the same way it would off a real enum member) — a bare
        # object with a `.value` attribute satisfies both, whereas
        # `SimpleNamespace` doesn't: it defines `__eq__` without `__hash__`,
        # which makes instances unhashable.
        class _UnregisteredSourceType:
            value = "unregistered"

        data_source.source_type = _UnregisteredSourceType()  # type: ignore[assignment]

        with pytest.raises(UnsupportedSourceTypeError):
            registry.build(data_source=data_source, secrets={})
