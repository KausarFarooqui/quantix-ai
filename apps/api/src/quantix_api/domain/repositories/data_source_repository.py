"""Abstract repository port for ``DataSource`` aggregates."""

from __future__ import annotations

from abc import abstractmethod
from uuid import UUID

from quantix_api.domain.entities.data_source import DataSource
from quantix_api.domain.repositories.base import AbstractRepository


class DataSourceRepository(AbstractRepository[DataSource]):
    @abstractmethod
    async def list_for_tenant(self, tenant_id: UUID) -> list[DataSource]:
        raise NotImplementedError  # pragma: no cover — abstract; the concrete repository overrides this
