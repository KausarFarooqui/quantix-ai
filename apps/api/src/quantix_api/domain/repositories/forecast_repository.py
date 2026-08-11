"""Abstract repository port for ``Forecast`` aggregates."""

from __future__ import annotations

from abc import abstractmethod
from uuid import UUID

from quantix_api.domain.entities.forecast import Forecast
from quantix_api.domain.repositories.base import AbstractRepository


class ForecastRepository(AbstractRepository[Forecast]):
    @abstractmethod
    async def list_for_dataset(self, dataset_id: UUID) -> list[Forecast]:
        raise NotImplementedError  # pragma: no cover — abstract; the concrete repository overrides this

    @abstractmethod
    async def list_for_tenant(self, tenant_id: UUID) -> list[Forecast]:
        raise NotImplementedError  # pragma: no cover — abstract; the concrete repository overrides this
