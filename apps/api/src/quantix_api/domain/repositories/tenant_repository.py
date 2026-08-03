"""Abstract repository port for ``Tenant`` aggregates."""

from __future__ import annotations

from abc import abstractmethod

from quantix_api.domain.entities.tenant import Tenant
from quantix_api.domain.repositories.base import AbstractRepository


class TenantRepository(AbstractRepository[Tenant]):
    @abstractmethod
    async def get_by_slug(self, slug: str) -> Tenant | None:
        raise NotImplementedError  # pragma: no cover — abstract; the concrete repository overrides this

    @abstractmethod
    async def slug_exists(self, slug: str) -> bool:
        raise NotImplementedError  # pragma: no cover — abstract; the concrete repository overrides this
