"""In-memory fakes for forecasting unit tests.

Named ``_forecasting_fakes.py`` — see ``tests/unit/auth/_auth_fakes.py``'s
docstring for why every fakes module in this test tree has a
directory-unique name (pytest's rootless import mode collides same-named
modules across directories).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pyarrow as pa

from quantix_api.domain.entities.dataset import Dataset
from quantix_api.domain.entities.forecast import Forecast
from quantix_api.domain.exceptions.base import EntityNotFoundError


class FakeDatasetStorage:
    def __init__(self) -> None:
        self._tables: dict[str, pa.Table] = {}

    def put(self, storage_uri: str, table: pa.Table) -> None:
        self._tables[storage_uri] = table

    def write(self, *, tenant_id: UUID, dataset_id: UUID, table: pa.Table) -> tuple[str, int]:
        uri = f"memory://{tenant_id}/{dataset_id}"
        self._tables[uri] = table
        return uri, table.nbytes

    def read_preview(self, *, storage_uri: str, limit: int = 100) -> pa.Table:
        return self._tables[storage_uri].slice(0, limit)

    def query(self, *, storage_uri: str, sql: str, limit: int = 1000) -> pa.Table:
        return self._tables[storage_uri].slice(0, limit)

    def delete(self, *, storage_uri: str) -> None:
        self._tables.pop(storage_uri, None)


class FakeDatasetRepository:
    def __init__(self, *, datasets: dict[UUID, Dataset] | None = None) -> None:
        self.store: dict[UUID, Dataset] = dict(datasets or {})

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


class FakeForecastRepository:
    def __init__(self) -> None:
        self.store: dict[UUID, Forecast] = {}

    async def get_by_id(self, entity_id: UUID) -> Forecast | None:
        return self.store.get(entity_id)

    async def add(self, entity: Forecast) -> Forecast:
        self.store[entity.id] = entity
        return entity

    async def update(self, entity: Forecast) -> Forecast:
        if entity.id not in self.store:
            raise EntityNotFoundError("Forecast", entity.id)
        self.store[entity.id] = entity
        return entity

    async def delete(self, entity_id: UUID) -> None:
        self.store.pop(entity_id, None)

    async def list_for_dataset(self, dataset_id: UUID) -> list[Forecast]:
        return [f for f in self.store.values() if f.dataset_id == dataset_id]

    async def list_for_tenant(self, tenant_id: UUID) -> list[Forecast]:
        return [f for f in self.store.values() if f.tenant_id == tenant_id]


class FakeAuditLogger:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    async def record(self, **kwargs: Any) -> None:
        self.records.append(kwargs)
