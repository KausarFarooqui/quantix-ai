"""Concrete SQLAlchemy implementation of ``domain.repositories.tenant_repository.TenantRepository``."""

from __future__ import annotations

from sqlalchemy import select

from quantix_api.domain.entities.tenant import Tenant
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.domain.repositories.tenant_repository import TenantRepository
from quantix_api.infrastructure.database.models.tenant import TenantModel
from quantix_api.infrastructure.database.repositories.sqlalchemy_repository import (
    SQLAlchemyRepository,
)


class SqlAlchemyTenantRepository(SQLAlchemyRepository[Tenant, TenantModel], TenantRepository):
    model = TenantModel

    def _to_entity(self, record: TenantModel) -> Tenant:
        return Tenant(
            id=record.id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            name=record.name,
            slug=record.slug,
            plan=record.plan,
            status=record.status,
        )

    def _to_model(self, entity: Tenant) -> TenantModel:
        return TenantModel(
            id=entity.id,
            name=entity.name,
            slug=entity.slug,
            plan=entity.plan,
            status=entity.status,
        )

    async def get_by_slug(self, slug: str) -> Tenant | None:
        stmt = select(TenantModel).where(TenantModel.slug == slug)
        record = (await self._session.scalars(stmt)).first()
        return self._to_entity(record) if record is not None else None

    async def slug_exists(self, slug: str) -> bool:
        stmt = select(TenantModel.id).where(TenantModel.slug == slug).limit(1)
        result = await self._session.scalars(stmt)
        return result.first() is not None

    async def update(self, entity: Tenant) -> Tenant:
        record = await self._session.get(TenantModel, entity.id)
        if record is None:
            raise EntityNotFoundError("Tenant", entity.id)
        record.name = entity.name
        record.slug = entity.slug
        record.plan = entity.plan
        record.status = entity.status
        await self._session.flush()
        await self._session.refresh(record)
        return self._to_entity(record)
