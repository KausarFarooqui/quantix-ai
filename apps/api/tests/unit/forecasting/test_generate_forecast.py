"""Unit tests for GenerateForecastUseCase — pure in-memory fakes, no DB.

Exercises the real forecasting engine (statsmodels ETSModel and the
linear-trend fallback), not a mocked-away version of it — same convention
``test_automl_agent.py`` uses for real scikit-learn training.
"""

from __future__ import annotations

from uuid import uuid4

import pyarrow as pa
import pytest
from _forecasting_fakes import (
    FakeAuditLogger,
    FakeDatasetRepository,
    FakeDatasetStorage,
    FakeForecastRepository,
)

from quantix_api.application.use_cases.generate_forecast import (
    MIN_POINTS_FOR_HOLT_WINTERS,
    GenerateForecastUseCase,
)
from quantix_api.domain.entities.dataset import Dataset, DatasetStatus
from quantix_api.domain.entities.forecast import ForecastMethod
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.domain.exceptions.connectors import DatasetNotReadyError
from quantix_api.domain.exceptions.forecasting import (
    InsufficientDataForForecastError,
    NonNumericForecastColumnError,
    UnknownForecastColumnError,
)


def _ready_dataset(*, tenant_id) -> Dataset:
    return Dataset(
        tenant_id=tenant_id,
        data_source_id=uuid4(),
        name="revenue",
        table_identifier="revenue",
        storage_uri="uri",
        status=DatasetStatus.READY,
        row_count=10,
    )


def _build(*, dataset: Dataset | None, table: pa.Table | None = None):
    tenant_id = dataset.tenant_id if dataset else uuid4()
    dataset_repo = FakeDatasetRepository(datasets={dataset.id: dataset} if dataset else {})
    storage = FakeDatasetStorage()
    if dataset is not None and table is not None:
        storage.put(dataset.storage_uri, table)
    forecast_repo = FakeForecastRepository()
    audit_logger = FakeAuditLogger()
    use_case = GenerateForecastUseCase(
        dataset_repo=dataset_repo,
        dataset_storage=storage,
        forecast_repo=forecast_repo,
        audit_logger=audit_logger,
    )
    return use_case, tenant_id, forecast_repo, audit_logger


class TestGenerateForecastUseCase:
    async def test_short_series_uses_linear_trend_and_persists(self) -> None:
        dataset = _ready_dataset(tenant_id=uuid4())
        table = pa.table({"revenue": [10.0, 20.0, 30.0, 40.0]})
        use_case, tenant_id, forecast_repo, audit_logger = _build(dataset=dataset, table=table)

        forecast = await use_case.execute(
            tenant_id=tenant_id,
            actor_user_id=uuid4(),
            dataset_id=dataset.id,
            target_column="revenue",
            periods=3,
        )

        assert forecast.method is ForecastMethod.LINEAR_TREND
        assert forecast.historical_points == 4
        assert len(forecast.points) == 3
        assert forecast.id in forecast_repo.store
        assert forecast.points[0].value > 40  # continues the +10/period trend
        assert any(r["action"].value == "forecast.generated" for r in audit_logger.records)

    async def test_long_series_uses_holt_winters_with_a_real_interval(self) -> None:
        dataset = _ready_dataset(tenant_id=uuid4())
        values = [float(50 + 2 * i) for i in range(MIN_POINTS_FOR_HOLT_WINTERS + 5)]
        table = pa.table({"revenue": values})
        use_case, tenant_id, _, _ = _build(dataset=dataset, table=table)

        forecast = await use_case.execute(
            tenant_id=tenant_id,
            actor_user_id=uuid4(),
            dataset_id=dataset.id,
            target_column="revenue",
            periods=4,
        )

        assert forecast.method is ForecastMethod.HOLT_WINTERS
        assert len(forecast.points) == 4
        for point in forecast.points:
            assert point.lower < point.upper

    async def test_sorts_by_time_column_when_given(self) -> None:
        dataset = _ready_dataset(tenant_id=uuid4())
        # Deliberately out of chronological order in storage.
        table = pa.table({"day": [3, 1, 2, 4], "revenue": [40.0, 10.0, 20.0, 50.0]})
        use_case, tenant_id, _, _ = _build(dataset=dataset, table=table)

        forecast = await use_case.execute(
            tenant_id=tenant_id,
            actor_user_id=uuid4(),
            dataset_id=dataset.id,
            target_column="revenue",
            time_column="day",
            periods=1,
        )

        # Sorted by day, the series is 10,20,30(day3->40 wait) — recompute:
        # day order 1,2,3,4 -> revenue 10,20,40,50: still increasing, so the
        # single forecast point should continue upward past the last value.
        assert forecast.points[0].value > 50

    async def test_unknown_dataset_raises_not_found(self) -> None:
        use_case, tenant_id, _, _ = _build(dataset=None)

        with pytest.raises(EntityNotFoundError):
            await use_case.execute(
                tenant_id=tenant_id,
                actor_user_id=uuid4(),
                dataset_id=uuid4(),
                target_column="revenue",
                periods=1,
            )

    async def test_another_tenants_dataset_raises_not_found(self) -> None:
        dataset = _ready_dataset(tenant_id=uuid4())
        use_case, _, _, _ = _build(dataset=dataset, table=pa.table({"revenue": [1.0, 2.0]}))

        with pytest.raises(EntityNotFoundError):
            await use_case.execute(
                tenant_id=uuid4(),  # a different tenant
                actor_user_id=uuid4(),
                dataset_id=dataset.id,
                target_column="revenue",
                periods=1,
            )

    async def test_dataset_not_ready_raises(self) -> None:
        dataset = Dataset(
            tenant_id=uuid4(),
            data_source_id=uuid4(),
            name="revenue",
            table_identifier="revenue",
            status=DatasetStatus.PROCESSING,
        )
        use_case, tenant_id, _, _ = _build(dataset=dataset)

        with pytest.raises(DatasetNotReadyError):
            await use_case.execute(
                tenant_id=tenant_id,
                actor_user_id=uuid4(),
                dataset_id=dataset.id,
                target_column="revenue",
                periods=1,
            )

    async def test_unknown_column_raises(self) -> None:
        dataset = _ready_dataset(tenant_id=uuid4())
        use_case, tenant_id, _, _ = _build(
            dataset=dataset, table=pa.table({"revenue": [1.0, 2.0, 3.0]})
        )

        with pytest.raises(UnknownForecastColumnError):
            await use_case.execute(
                tenant_id=tenant_id,
                actor_user_id=uuid4(),
                dataset_id=dataset.id,
                target_column="does_not_exist",
                periods=1,
            )

    async def test_non_numeric_column_raises(self) -> None:
        dataset = _ready_dataset(tenant_id=uuid4())
        table = pa.table({"region": ["east", "west", "north"]})
        use_case, tenant_id, _, _ = _build(dataset=dataset, table=table)

        with pytest.raises(NonNumericForecastColumnError):
            await use_case.execute(
                tenant_id=tenant_id,
                actor_user_id=uuid4(),
                dataset_id=dataset.id,
                target_column="region",
                periods=1,
            )

    async def test_too_few_points_raises(self) -> None:
        dataset = _ready_dataset(tenant_id=uuid4())
        table = pa.table({"revenue": [10.0]})
        use_case, tenant_id, _, _ = _build(dataset=dataset, table=table)

        with pytest.raises(InsufficientDataForForecastError):
            await use_case.execute(
                tenant_id=tenant_id,
                actor_user_id=uuid4(),
                dataset_id=dataset.id,
                target_column="revenue",
                periods=1,
            )

    async def test_periods_are_capped(self) -> None:
        dataset = _ready_dataset(tenant_id=uuid4())
        table = pa.table({"revenue": [10.0, 20.0, 30.0, 40.0]})
        use_case, tenant_id, _, _ = _build(dataset=dataset, table=table)

        forecast = await use_case.execute(
            tenant_id=tenant_id,
            actor_user_id=uuid4(),
            dataset_id=dataset.id,
            target_column="revenue",
            periods=999,
        )

        assert len(forecast.points) <= 52
