"""Concrete SQLAlchemy implementation of
``domain.repositories.dataset_repository.DatasetRepository``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from quantix_api.domain.entities.dataset import Dataset, DatasetColumn, DatasetColumnType
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.domain.repositories.dataset_repository import DatasetRepository
from quantix_api.infrastructure.database.models.dataset import DatasetModel
from quantix_api.infrastructure.database.repositories.sqlalchemy_repository import (
    SQLAlchemyRepository,
)


class SqlAlchemyDatasetRepository(SQLAlchemyRepository[Dataset, DatasetModel], DatasetRepository):
    model = DatasetModel

    def _to_entity(self, record: DatasetModel) -> Dataset:
        return Dataset(
            id=record.id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            tenant_id=record.tenant_id,
            data_source_id=record.data_source_id,
            name=record.name,
            table_identifier=record.table_identifier,
            schema=[
                DatasetColumn(
                    name=column["name"],
                    data_type=DatasetColumnType(column["data_type"]),
                    nullable=column.get("nullable", True),
                )
                for column in (record.schema_json or [])
            ],
            row_count=record.row_count,
            size_bytes=record.size_bytes,
            storage_uri=record.storage_uri,
            status=record.status,
            status_message=record.status_message,
            last_synced_at=record.last_synced_at,
        )

    def _to_model(self, entity: Dataset) -> DatasetModel:
        return DatasetModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            data_source_id=entity.data_source_id,
            name=entity.name,
            table_identifier=entity.table_identifier,
            schema_json=[
                {"name": c.name, "data_type": c.data_type.value, "nullable": c.nullable}
                for c in entity.schema
            ],
            row_count=entity.row_count,
            size_bytes=entity.size_bytes,
            storage_uri=entity.storage_uri,
            status=entity.status,
            status_message=entity.status_message,
            last_synced_at=entity.last_synced_at,
        )

    async def list_for_tenant(self, tenant_id: UUID) -> list[Dataset]:
        stmt = (
            select(DatasetModel)
            .where(DatasetModel.tenant_id == tenant_id)
            .order_by(DatasetModel.created_at.desc())
        )
        result = await self._session.scalars(stmt)
        return [self._to_entity(record) for record in result.all()]

    async def list_for_data_source(self, data_source_id: UUID) -> list[Dataset]:
        stmt = select(DatasetModel).where(DatasetModel.data_source_id == data_source_id)
        result = await self._session.scalars(stmt)
        return [self._to_entity(record) for record in result.all()]

    async def update(self, entity: Dataset) -> Dataset:
        record = await self._session.get(DatasetModel, entity.id)
        if record is None:
            raise EntityNotFoundError("Dataset", entity.id)
        record.name = entity.name
        record.table_identifier = entity.table_identifier
        record.schema_json = [
            {"name": c.name, "data_type": c.data_type.value, "nullable": c.nullable}
            for c in entity.schema
        ]
        record.row_count = entity.row_count
        record.size_bytes = entity.size_bytes
        record.storage_uri = entity.storage_uri
        record.status = entity.status
        record.status_message = entity.status_message
        record.last_synced_at = entity.last_synced_at
        await self._session.flush()
        await self._session.refresh(record)
        return self._to_entity(record)
