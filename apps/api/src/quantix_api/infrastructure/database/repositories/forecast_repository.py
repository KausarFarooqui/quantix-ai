"""Concrete SQLAlchemy implementation of
``domain.repositories.forecast_repository.ForecastRepository``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from quantix_api.domain.entities.forecast import Forecast, ForecastPoint
from quantix_api.domain.repositories.forecast_repository import ForecastRepository
from quantix_api.infrastructure.database.models.forecast import ForecastModel
from quantix_api.infrastructure.database.repositories.sqlalchemy_repository import (
    SQLAlchemyRepository,
)


class SqlAlchemyForecastRepository(
    SQLAlchemyRepository[Forecast, ForecastModel], ForecastRepository
):
    model = ForecastModel

    def _to_entity(self, record: ForecastModel) -> Forecast:
        return Forecast(
            id=record.id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            tenant_id=record.tenant_id,
            dataset_id=record.dataset_id,
            created_by_user_id=record.created_by_user_id,
            conversation_id=record.conversation_id,
            target_column=record.target_column,
            time_column=record.time_column,
            method=record.method,
            historical_points=record.historical_points,
            points=[
                ForecastPoint(
                    period=point["period"],
                    value=point["value"],
                    lower=point["lower"],
                    upper=point["upper"],
                )
                for point in (record.points_json or [])
            ],
        )

    def _to_model(self, entity: Forecast) -> ForecastModel:
        return ForecastModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            dataset_id=entity.dataset_id,
            created_by_user_id=entity.created_by_user_id,
            conversation_id=entity.conversation_id,
            target_column=entity.target_column,
            time_column=entity.time_column,
            method=entity.method,
            historical_points=entity.historical_points,
            points_json=[
                {"period": p.period, "value": p.value, "lower": p.lower, "upper": p.upper}
                for p in entity.points
            ],
        )

    async def list_for_dataset(self, dataset_id: UUID) -> list[Forecast]:
        stmt = (
            select(ForecastModel)
            .where(ForecastModel.dataset_id == dataset_id)
            .order_by(ForecastModel.created_at.desc())
        )
        result = await self._session.scalars(stmt)
        return [self._to_entity(record) for record in result.all()]

    async def list_for_tenant(self, tenant_id: UUID) -> list[Forecast]:
        stmt = (
            select(ForecastModel)
            .where(ForecastModel.tenant_id == tenant_id)
            .order_by(ForecastModel.created_at.desc())
        )
        result = await self._session.scalars(stmt)
        return [self._to_entity(record) for record in result.all()]
