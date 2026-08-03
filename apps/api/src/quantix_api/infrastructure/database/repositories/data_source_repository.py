"""Concrete SQLAlchemy implementation of
``domain.repositories.data_source_repository.DataSourceRepository``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from quantix_api.domain.entities.data_source import DataSource
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.domain.repositories.data_source_repository import DataSourceRepository
from quantix_api.infrastructure.database.models.data_source import DataSourceModel
from quantix_api.infrastructure.database.repositories.sqlalchemy_repository import (
    SQLAlchemyRepository,
)


class SqlAlchemyDataSourceRepository(
    SQLAlchemyRepository[DataSource, DataSourceModel], DataSourceRepository
):
    model = DataSourceModel

    def _to_entity(self, record: DataSourceModel) -> DataSource:
        return DataSource(
            id=record.id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            tenant_id=record.tenant_id,
            name=record.name,
            source_type=record.source_type,
            config=record.config,
            encrypted_secrets=record.encrypted_secrets,
            status=record.status,
            last_tested_at=record.last_tested_at,
            last_test_error=record.last_test_error,
            created_by_user_id=record.created_by_user_id,
        )

    def _to_model(self, entity: DataSource) -> DataSourceModel:
        return DataSourceModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            name=entity.name,
            source_type=entity.source_type,
            config=entity.config,
            encrypted_secrets=entity.encrypted_secrets,
            status=entity.status,
            last_tested_at=entity.last_tested_at,
            last_test_error=entity.last_test_error,
            created_by_user_id=entity.created_by_user_id,
        )

    async def list_for_tenant(self, tenant_id: UUID) -> list[DataSource]:
        stmt = (
            select(DataSourceModel)
            .where(DataSourceModel.tenant_id == tenant_id)
            .order_by(DataSourceModel.created_at.desc())
        )
        result = await self._session.scalars(stmt)
        return [self._to_entity(record) for record in result.all()]

    async def update(self, entity: DataSource) -> DataSource:
        record = await self._session.get(DataSourceModel, entity.id)
        if record is None:
            raise EntityNotFoundError("DataSource", entity.id)
        record.name = entity.name
        record.config = entity.config
        record.encrypted_secrets = entity.encrypted_secrets
        record.status = entity.status
        record.last_tested_at = entity.last_tested_at
        record.last_test_error = entity.last_test_error
        await self._session.flush()
        await self._session.refresh(record)
        return self._to_entity(record)
