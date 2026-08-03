"""Abstract repository port for ``Dataset`` aggregates."""

from __future__ import annotations

from abc import abstractmethod
from uuid import UUID

from quantix_api.domain.entities.dataset import Dataset
from quantix_api.domain.repositories.base import AbstractRepository


class DatasetRepository(AbstractRepository[Dataset]):
    @abstractmethod
    async def list_for_tenant(self, tenant_id: UUID) -> list[Dataset]:
        raise NotImplementedError  # pragma: no cover — abstract; the concrete repository overrides this

    @abstractmethod
    async def list_for_data_source(self, data_source_id: UUID) -> list[Dataset]:
        raise NotImplementedError  # pragma: no cover — abstract; the concrete repository overrides this
