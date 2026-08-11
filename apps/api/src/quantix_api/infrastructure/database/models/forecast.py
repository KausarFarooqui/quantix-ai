"""ORM model for forecasts."""

from __future__ import annotations

import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from quantix_api.domain.entities.forecast import ForecastMethod
from quantix_api.infrastructure.database.models.base import (
    PORTABLE_JSON,
    Base,
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class ForecastModel(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "forecasts"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    target_column: Mapped[str] = mapped_column(String(255), nullable=False)
    time_column: Mapped[str | None] = mapped_column(String(255), nullable=True)
    method: Mapped[ForecastMethod] = mapped_column(
        Enum(ForecastMethod, name="forecast_method", native_enum=True), nullable=False
    )
    historical_points: Mapped[int] = mapped_column(Integer, nullable=False)
    # Serialized list[{"period", "value", "lower", "upper"}] — small
    # (<= MAX_FORECAST_PERIODS entries), so one JSON column rather than a
    # child table, same trade-off `Dataset.schema_json` already makes.
    points_json: Mapped[list] = mapped_column(PORTABLE_JSON, nullable=False, default=list)
