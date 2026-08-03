"""Unit tests for SqlDatabaseConnector — run against real SQLite rather
than mocks, since SQLite is one of the five dialects this single class is
meant to support and needs zero external infrastructure to test against.
"""

from __future__ import annotations

from sqlalchemy import create_engine, text

from quantix_api.domain.entities.data_source import SourceType
from quantix_api.domain.entities.dataset import DatasetColumnType
from quantix_api.infrastructure.connectors.sql_connector import SqlDatabaseConnector


def _seeded_connector() -> SqlDatabaseConnector:
    connector = SqlDatabaseConnector(
        source_type=SourceType.SQLITE, config={"database": ":memory:"}, secrets={}
    )
    # Force the connector to create (and cache) its engine, then seed data
    # on that same engine/connection so it's visible to later calls.
    engine = connector._get_engine()  # noqa: SLF001 — deliberate, see note above
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE orders (id INTEGER PRIMARY KEY, customer TEXT, total REAL)")
        )
        connection.execute(
            text("INSERT INTO orders (id, customer, total) VALUES (1, 'Alice', 19.99), (2, 'Bob', 42.5)")
        )
    return connector


class TestConnection:
    def test_succeeds_against_a_real_database(self) -> None:
        connector = _seeded_connector()
        assert connector.test_connection().success is True

    def test_fails_against_an_unreachable_database(self) -> None:
        connector = SqlDatabaseConnector(
            source_type=SourceType.SQLITE,
            config={"database": "/nonexistent/path/does-not-exist.db"},
            secrets={},
        )
        # SQLite will happily create a new file at a valid path, so use an
        # invalid path (no such directory) to force a real connection error.
        result = connector.test_connection()
        assert result.success is False
        assert result.error


class TestDiscover:
    def test_lists_tables_with_columns(self) -> None:
        connector = _seeded_connector()

        tables = connector.discover()

        assert len(tables) == 1
        assert tables[0].identifier == "orders"
        column_names = {c.name for c in tables[0].columns}
        assert column_names == {"id", "customer", "total"}

    def test_maps_sql_types_to_normalized_types(self) -> None:
        connector = _seeded_connector()
        columns = {c.name: c.data_type for c in connector.discover()[0].columns}

        assert columns["id"] == DatasetColumnType.INTEGER
        assert columns["customer"] == DatasetColumnType.STRING
        assert columns["total"] == DatasetColumnType.FLOAT


class TestExtract:
    def test_extracts_full_table(self) -> None:
        connector = _seeded_connector()
        table = connector.extract("orders")
        assert table.num_rows == 2
        assert set(table.column("customer").to_pylist()) == {"Alice", "Bob"}

    def test_respects_limit(self) -> None:
        connector = _seeded_connector()
        table = connector.extract("orders", limit=1)
        assert table.num_rows == 1

    def test_accepts_a_raw_select_query(self) -> None:
        connector = _seeded_connector()
        table = connector.extract("SELECT customer FROM orders WHERE total > 30")
        assert table.num_rows == 1
        assert table.column("customer").to_pylist() == ["Bob"]


class TestUrlBuilding:
    def test_sqlite_url(self) -> None:
        connector = SqlDatabaseConnector(
            source_type=SourceType.SQLITE, config={"database": "/tmp/quantix-test.db"}, secrets={}
        )
        assert connector._build_url() == "sqlite:////tmp/quantix-test.db"  # noqa: SLF001

    def test_postgres_url_includes_credentials(self) -> None:
        connector = SqlDatabaseConnector(
            source_type=SourceType.POSTGRESQL,
            config={"host": "db.internal", "port": 5432, "database": "quantix"},
            secrets={"username": "admin", "password": "p@ss"},
        )
        url = connector._build_url()  # noqa: SLF001
        assert url.startswith("postgresql+psycopg://admin:")
        assert "db.internal:5432/quantix" in url
