"""Pydantic request/response schemas for the forecasts endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from quantix_api.application.use_cases.generate_forecast import MAX_FORECAST_PERIODS


class ForecastCreateRequest(BaseModel):
    dataset_id: UUID
    target_column: str = Field(min_length=1)
    time_column: str | None = Field(
        default=None,
        description="Optional column to sort by first, if the dataset's row order doesn't "
        "already reflect chronological order.",
    )
    periods: int = Field(default=5, ge=1, le=MAX_FORECAST_PERIODS)


class ForecastPointResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    period: int
    value: float
    lower: float
    upper: float


class ForecastResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    dataset_id: UUID
    conversation_id: UUID | None
    target_column: str
    time_column: str | None
    method: str
    historical_points: int
    points: list[ForecastPointResponse]
    created_at: datetime
