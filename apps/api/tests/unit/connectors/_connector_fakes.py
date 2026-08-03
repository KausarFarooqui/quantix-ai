"""In-memory fakes for connector-layer use-case tests.

Named ``_connector_fakes.py``, not the generic ``_fakes.py`` — see the
docstring in ``tests/unit/auth/_auth_fakes.py`` for why every fakes
module in this test tree has a directory-unique name (pytest's rootless
import mode collides same-named modules across directories).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pyarrow as pa

from quantix_api.application.interfaces.connector import ConnectionTestResult, TableSchema
from quantix_api.domain.entities.data_source import DataSource
from quantix_api.domain.entities.dataset import Dataset
from quantix_api.domain.exceptions.base import EntityNotFoundError


class FakeDataSourceRepository:
    def __init__(self) -> None:
        self.store: dict[UUID, DataSource] = {}

    async def get_by_id(self, entity_id: UUID) -> DataSource | None:
        return self.store.get(entity_id)

    async def add(self, entity: DataSource) -> DataSource:
        self.store[entity.id] = entity
        return entity

    async def update(self, entity: DataSource) -> DataSource:
        if entity.id not in self.store:
            raise EntityNotFoundError("DataSource", entity.id)
        self.store[entity.id] = entity
        return entity

    async def delete(self, entity_id: UUID) -> None:
        self.store.pop(entity_id, None)

    async def list_for_tenant(self, tenant_id: UUID) -> list[DataSource]:
        return [ds for ds in self.store.values() if ds.tenant_id == tenant_id]


class FakeDatasetRepository:
    def __init__(self) -> None:
        self.store: dict[UUID, Dataset] = {}

    async def get_by_id(self, entity_id: UUID) -> Dataset | None:
        return self.store.get(entity_id)

    async def add(self, entity: Dataset) -> Dataset:
        self.store[entity.id] = entity
        return entity

    async def update(self, entity: Dataset) -> Dataset:
        if entity.id not in self.store:
            raise EntityNotFoundError("Dataset", entity.id)
        self.store[entity.id] = entity
        return entity

    async def delete(self, entity_id: UUID) -> None:
        self.store.pop(entity_id, None)

    async def list_for_tenant(self, tenant_id: UUID) -> list[Dataset]:
        return [d for d in self.store.values() if d.tenant_id == tenant_id]

    async def list_for_data_source(self, data_source_id: UUID) -> list[Dataset]:
        return [d for d in self.store.values() if d.data_source_id == data_source_id]


class FakeDatasetStorage:
    """Stores tables in memory, keyed by a fake "path" it hands back."""

    def __init__(self) -> None:
        self._tables: dict[str, pa.Table] = {}
        self._next_id = 0

    def write(self, *, tenant_id: UUID, dataset_id: UUID, table: pa.Table) -> tuple[str, int]:
        uri = f"memory://{tenant_id}/{dataset_id}"
        self._tables[uri] = table
        return uri, table.nbytes

    def read_preview(self, *, storage_uri: str, limit: int = 100) -> pa.Table:
        table = self._tables[storage_uri]
        return table.slice(0, limit)

    def query(self, *, storage_uri: str, sql: str, limit: int = 1000) -> pa.Table:
        # Fake is not a SQL engine — good enough for use-case-level tests
        # that only need "some rows come back," never a real WHERE/GROUP BY.
        table = self._tables[storage_uri]
        return table.slice(0, limit)

    def delete(self, *, storage_uri: str) -> None:
        self._tables.pop(storage_uri, None)


class FakeFileStorage:
    def __init__(self) -> None:
        self._files: dict[str, bytes] = {}
        self._next_id = 0

    def save(self, *, tenant_id: UUID, filename: str, content: bytes) -> str:
        self._next_id += 1
        path = f"memory://{tenant_id}/{self._next_id}_{filename}"
        self._files[path] = content
        return path

    def read(self, *, storage_path: str) -> bytes:
        return self._files[storage_path]

    def delete(self, *, storage_path: str) -> None:
        self._files.pop(storage_path, None)


class FakeConnector:
    """A canned connector — returns a fixed Arrow table regardless of
    which table_identifier is requested, and can be configured to fail.
    """

    def __init__(self, *, table: pa.Table | None = None, should_fail: bool = False) -> None:
        self._table = table or pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        self._should_fail = should_fail

    def test_connection(self) -> ConnectionTestResult:
        if self._should_fail:
            return ConnectionTestResult(success=False, error="boom")
        return ConnectionTestResult(success=True)

    def discover(self) -> list[TableSchema]:
        return [TableSchema(identifier="fake_table", columns=[], row_count_estimate=self._table.num_rows)]

    def extract(self, table_identifier: str, *, limit: int | None = None) -> pa.Table:
        if self._should_fail:
            raise RuntimeError("extraction boom")
        return self._table.slice(0, limit) if limit is not None else self._table


class FakeConnectorFactory:
    def __init__(self, connector: FakeConnector | None = None) -> None:
        self.connector = connector or FakeConnector()
        self.built_with: list[tuple[DataSource, dict[str, Any]]] = []

    def build(self, *, data_source: DataSource, secrets: dict[str, Any]):  # noqa: ANN201
        self.built_with.append((data_source, secrets))
        return self.connector


class FakeAuditLogger:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    async def record(self, **kwargs: Any) -> None:
        self.records.append(kwargs)


class FakeCredentialCipher:
    """No-op "encryption" — just JSON-in-a-box — fine for tests that don't
    exercise the real crypto (see test_credential_cipher.py for that).
    """

    def encrypt(self, secrets: dict[str, Any]) -> str:
        import json

        return json.dumps(secrets)

    def decrypt(self, ciphertext: str) -> dict[str, Any]:
        import json

        return json.loads(ciphertext)
