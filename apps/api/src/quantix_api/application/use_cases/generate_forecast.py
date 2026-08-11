"""Generate a real time-series forecast for one numeric dataset column.

Primary method is Holt-Winters exponential smoothing (damped trend, no
seasonality — the source column's actual time frequency isn't known, so
guessing a seasonal period would be worse than not modeling one) via
statsmodels' state-space ``ETSModel``, which gives a real prediction
interval, not just a point forecast. Falls back to a plain least-squares
linear-trend extrapolation — the method this replaced as the *only*
method (see ``infrastructure.agents.tools``'s prior ``forecast_series``
tool) — for series too short for Holt-Winters to fit meaningfully, with
that fallback's interval clearly documented as a heuristic rather than a
statistical one.

Deliberately synchronous, like ``SendMessageUseCase`` and the AutoML
agent's training: fitting either method against up to
``MAX_FORECAST_ROWS`` points is fast enough to complete within one HTTP
request/agent-turn without a Celery hop.
"""

from __future__ import annotations

import math
from uuid import UUID

import anyio
import numpy as np
import pandas as pd

from quantix_api.application.interfaces.audit_logger import AuditLogger
from quantix_api.application.interfaces.dataset_storage import DatasetStorage
from quantix_api.domain.entities.audit_log import AuditAction
from quantix_api.domain.entities.dataset import DatasetStatus
from quantix_api.domain.entities.forecast import Forecast, ForecastMethod, ForecastPoint
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.domain.exceptions.connectors import DatasetNotReadyError
from quantix_api.domain.exceptions.forecasting import (
    InsufficientDataForForecastError,
    NonNumericForecastColumnError,
    UnknownForecastColumnError,
)
from quantix_api.domain.repositories.dataset_repository import DatasetRepository
from quantix_api.domain.repositories.forecast_repository import ForecastRepository

MAX_FORECAST_ROWS = 5000
MIN_POINTS_FOR_ANY_FORECAST = 2
# Below this, Holt-Winters is skipped entirely rather than attempted and
# caught on failure — verified empirically that ETSModel doesn't reliably
# *raise* on too-short series, it just fits something numerically
# unstable and prints a convergence warning, so an exception handler alone
# can't be trusted to catch this case.
MIN_POINTS_FOR_HOLT_WINTERS = 8
MAX_FORECAST_PERIODS = 52
CONFIDENCE_ALPHA = 0.10  # 90% interval


class GenerateForecastUseCase:
    def __init__(
        self,
        *,
        dataset_repo: DatasetRepository,
        dataset_storage: DatasetStorage,
        forecast_repo: ForecastRepository,
        audit_logger: AuditLogger,
    ) -> None:
        self._dataset_repo = dataset_repo
        self._dataset_storage = dataset_storage
        self._forecast_repo = forecast_repo
        self._audit_logger = audit_logger

    async def execute(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        dataset_id: UUID,
        target_column: str,
        periods: int,
        time_column: str | None = None,
        conversation_id: UUID | None = None,
    ) -> Forecast:
        dataset = await self._dataset_repo.get_by_id(dataset_id)
        if dataset is None or dataset.tenant_id != tenant_id:
            raise EntityNotFoundError("Dataset", dataset_id)
        if dataset.status is not DatasetStatus.READY or not dataset.storage_uri:
            raise DatasetNotReadyError(dataset_id, dataset.status.value)

        storage_uri = dataset.storage_uri
        table = await anyio.to_thread.run_sync(
            lambda: self._dataset_storage.read_preview(
                storage_uri=storage_uri, limit=MAX_FORECAST_ROWS
            )
        )

        column_names = table.column_names
        if target_column not in column_names:
            raise UnknownForecastColumnError(target_column, dataset_id)
        if time_column is not None and time_column not in column_names:
            raise UnknownForecastColumnError(time_column, dataset_id)

        dataframe = table.to_pandas()
        if time_column is not None:
            dataframe = dataframe.sort_values(time_column)

        try:
            numeric = dataframe[target_column].astype(float)
        except (TypeError, ValueError) as exc:
            raise NonNumericForecastColumnError(target_column) from exc
        series = numeric.dropna().to_numpy()

        if series.size < MIN_POINTS_FOR_ANY_FORECAST:
            raise InsufficientDataForForecastError(
                target_column, series.size, MIN_POINTS_FOR_ANY_FORECAST
            )

        capped_periods = min(periods, MAX_FORECAST_PERIODS)
        method, points = await anyio.to_thread.run_sync(lambda: _fit(series, capped_periods))

        forecast = await self._forecast_repo.add(
            Forecast(
                tenant_id=tenant_id,
                dataset_id=dataset_id,
                created_by_user_id=actor_user_id,
                conversation_id=conversation_id,
                target_column=target_column,
                time_column=time_column,
                method=method,
                historical_points=int(series.size),
                points=points,
            )
        )

        await self._audit_logger.record(
            action=AuditAction.FORECAST_GENERATED,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            resource_type="forecast",
            resource_id=str(forecast.id),
            metadata={
                "dataset_id": str(dataset_id),
                "target_column": target_column,
                "method": method.value,
            },
        )

        return forecast


def _fit(series: np.ndarray, periods: int) -> tuple[ForecastMethod, list[ForecastPoint]]:
    if series.size >= MIN_POINTS_FOR_HOLT_WINTERS:
        try:
            return ForecastMethod.HOLT_WINTERS, _holt_winters_forecast(series, periods)
        except Exception:  # noqa: BLE001 — any fit failure falls back to the simpler method
            pass
    return ForecastMethod.LINEAR_TREND, _linear_trend_forecast(series, periods)


def _holt_winters_forecast(series: np.ndarray, periods: int) -> list[ForecastPoint]:
    import warnings

    from statsmodels.tsa.exponential_smoothing.ets import ETSModel

    # ETSModel needs a pandas-indexed series (not a raw ndarray) for
    # get_prediction() to build its result frame — verified directly
    # against a bare ndarray raising AttributeError otherwise.
    indexed = pd.Series(series, index=pd.RangeIndex(series.size))

    with warnings.catch_warnings():
        # Convergence warnings on borderline series are expected and
        # harmless here — MIN_POINTS_FOR_HOLT_WINTERS already screens out
        # the sizes where a genuinely bad fit would matter.
        warnings.simplefilter("ignore")
        model = ETSModel(indexed, error="add", trend="add", damped_trend=True)
        fit = model.fit(disp=False)

    prediction = fit.get_prediction(start=series.size, end=series.size + periods - 1)
    summary = prediction.summary_frame(alpha=CONFIDENCE_ALPHA)
    return [
        ForecastPoint(
            period=i + 1,
            value=float(row["mean"]),
            lower=float(row["pi_lower"]),
            upper=float(row["pi_upper"]),
        )
        for i, (_, row) in enumerate(summary.iterrows())
    ]


def _linear_trend_forecast(series: np.ndarray, periods: int) -> list[ForecastPoint]:
    """Least-squares trend extrapolation. The interval here is a heuristic
    (residual spread, widening with distance from the last known point) —
    not a statistically rigorous prediction interval like Holt-Winters',
    and deliberately not presented as one.
    """
    x = np.arange(series.size)
    slope, intercept = np.polyfit(x, series, deg=1)
    residual_std = float(np.std(series - (slope * x + intercept)))

    points: list[ForecastPoint] = []
    for step in range(1, periods + 1):
        value = float(slope * (series.size + step - 1) + intercept)
        margin = 1.645 * residual_std * math.sqrt(1 + step / series.size)
        points.append(
            ForecastPoint(period=step, value=value, lower=value - margin, upper=value + margin)
        )
    return points
