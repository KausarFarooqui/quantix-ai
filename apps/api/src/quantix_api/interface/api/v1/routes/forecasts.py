"""Generate and list real, persisted time-series forecasts against a
dataset column — see ``application.use_cases.generate_forecast`` for the
engine and ``docs/adr`` for the design behind why this exists as a
standalone resource on top of the chat system's ``forecast_series`` tool
rather than only being reachable through a conversation.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from quantix_api.domain.entities.forecast import Forecast
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.interface.api.v1.dependencies.auth import CurrentUser
from quantix_api.interface.api.v1.dependencies.forecast_use_cases import (
    GenerateForecastUseCaseDep,
)
from quantix_api.interface.api.v1.dependencies.repositories import ForecastRepo
from quantix_api.interface.api.v1.schemas.forecasts import (
    ForecastCreateRequest,
    ForecastPointResponse,
    ForecastResponse,
)

router = APIRouter(prefix="/forecasts", tags=["forecasts"])


def to_forecast_response(forecast: Forecast) -> ForecastResponse:
    return ForecastResponse(
        id=forecast.id,
        dataset_id=forecast.dataset_id,
        conversation_id=forecast.conversation_id,
        target_column=forecast.target_column,
        time_column=forecast.time_column,
        method=forecast.method.value,
        historical_points=forecast.historical_points,
        points=[
            ForecastPointResponse(period=p.period, value=p.value, lower=p.lower, upper=p.upper)
            for p in forecast.points
        ],
        created_at=forecast.created_at,
    )


@router.post(
    "",
    response_model=ForecastResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a forecast for a numeric dataset column",
)
async def create_forecast(
    body: ForecastCreateRequest, use_case: GenerateForecastUseCaseDep, current_user: CurrentUser
) -> ForecastResponse:
    forecast = await use_case.execute(
        tenant_id=current_user.tenant_id,
        actor_user_id=current_user.id,
        dataset_id=body.dataset_id,
        target_column=body.target_column,
        time_column=body.time_column,
        periods=body.periods,
    )
    return to_forecast_response(forecast)


@router.get(
    "",
    response_model=list[ForecastResponse],
    summary="List forecasts for the current tenant, or for one dataset",
)
async def list_forecasts(
    forecast_repo: ForecastRepo, current_user: CurrentUser, dataset_id: UUID | None = None
) -> list[ForecastResponse]:
    forecasts = (
        await forecast_repo.list_for_dataset(dataset_id)
        if dataset_id is not None
        else await forecast_repo.list_for_tenant(current_user.tenant_id)
    )
    # `list_for_dataset` isn't tenant-scoped by itself (it's a lookup by
    # foreign key, not a repository method that takes a tenant_id) — filter
    # here rather than trust the query parameter alone, same reasoning as
    # every other cross-tenant guard in this codebase.
    return [to_forecast_response(f) for f in forecasts if f.tenant_id == current_user.tenant_id]


@router.get("/{forecast_id}", response_model=ForecastResponse, summary="Get a single forecast")
async def get_forecast(
    forecast_id: UUID, forecast_repo: ForecastRepo, current_user: CurrentUser
) -> ForecastResponse:
    forecast = await forecast_repo.get_by_id(forecast_id)
    if forecast is None or forecast.tenant_id != current_user.tenant_id:
        raise EntityNotFoundError("Forecast", forecast_id)
    return to_forecast_response(forecast)
