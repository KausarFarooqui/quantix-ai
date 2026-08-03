"""Generic SQLAlchemy repository implementation.

Aggregate-specific repositories (e.g. ``UserRepository``) subclass this and
supply the entity/model mapping functions, avoiding boilerplate CRUD code
duplication while keeping the domain layer's ``Repository`` port satisfied.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from quantix_api.domain.entities.base import Entity
from quantix_api.infrastructure.database.models.base import Base

EntityT = TypeVar("EntityT", bound=Entity)
ModelT = TypeVar("ModelT", bound=Base)


class SQLAlchemyRepository(Generic[EntityT, ModelT]):
    """Base class implementing CRUD against a SQLAlchemy model, translating
    to/from the equivalent domain entity at the boundary.
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @abstractmethod
    def _to_entity(self, record: ModelT) -> EntityT:
        """Map an ORM row to its domain entity."""
        raise NotImplementedError  # pragma: no cover — every concrete subclass overrides this

    @abstractmethod
    def _to_model(self, entity: EntityT) -> ModelT:
        """Map a domain entity to an ORM row for persistence."""
        raise NotImplementedError  # pragma: no cover — every concrete subclass overrides this

    async def get_by_id(self, entity_id: UUID) -> EntityT | None:
        record = await self._session.get(self.model, entity_id)
        return self._to_entity(record) if record is not None else None

    async def add(self, entity: EntityT) -> EntityT:
        record = self._to_model(entity)
        self._session.add(record)
        await self._session.flush()
        # Server-generated columns (created_at/updated_at's `server_default`)
        # aren't guaranteed to come back populated on `record` purely from
        # `flush()` on every dialect/driver combination — accessing an
        # unrefreshed, server-defaulted attribute afterwards can raise
        # `MissingGreenlet` under AsyncSession. An explicit refresh makes
        # this correct everywhere rather than relying on RETURNING support
        # being both present and auto-applied.
        await self._session.refresh(record)
        return self._to_entity(record)

    # Every concrete repository currently defines its own `update()`
    # (partial-field updates against an already-loaded record rather than a
    # blind `merge()`), so this generic version is unreachable today. Kept
    # as the documented default for a future repository that doesn't need
    # custom update semantics.
    async def update(self, entity: EntityT) -> EntityT:  # pragma: no cover
        record = await self._session.merge(self._to_model(entity))
        await self._session.flush()
        await self._session.refresh(record)
        return self._to_entity(record)

    async def delete(self, entity_id: UUID) -> None:
        record = await self._session.get(self.model, entity_id)
        if record is not None:
            await self._session.delete(record)
            await self._session.flush()

    async def list_all(self, *, limit: int = 100, offset: int = 0) -> list[EntityT]:
        stmt = select(self.model).limit(limit).offset(offset)
        result = await self._session.scalars(stmt)
        return [self._to_entity(record) for record in result.all()]
