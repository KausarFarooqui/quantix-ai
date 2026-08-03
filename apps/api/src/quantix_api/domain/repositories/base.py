"""Abstract repository interfaces (ports).

Defined in the domain layer per the Dependency Inversion Principle:
application/use-case code depends on these abstractions, and concrete
SQLAlchemy implementations live in ``infrastructure.database.repositories``
and are wired in at the composition root (``core.container``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, Protocol, TypeVar
from uuid import UUID

from quantix_api.domain.entities.base import Entity

EntityT = TypeVar("EntityT", bound=Entity)


class Repository(Protocol, Generic[EntityT]):
    """Minimal CRUD contract every aggregate repository must satisfy."""

    async def get_by_id(self, entity_id: UUID) -> EntityT | None: ...

    async def add(self, entity: EntityT) -> EntityT: ...

    async def update(self, entity: EntityT) -> EntityT: ...

    async def delete(self, entity_id: UUID) -> None: ...


class AbstractRepository(ABC, Generic[EntityT]):
    """Convenience ABC for repositories that want a concrete base class
    instead of structural typing via ``Repository``.
    """

    @abstractmethod
    async def get_by_id(self, entity_id: UUID) -> EntityT | None: ...

    @abstractmethod
    async def add(self, entity: EntityT) -> EntityT: ...

    @abstractmethod
    async def update(self, entity: EntityT) -> EntityT: ...

    @abstractmethod
    async def delete(self, entity_id: UUID) -> None: ...
