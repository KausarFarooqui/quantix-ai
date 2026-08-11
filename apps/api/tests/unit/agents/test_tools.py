"""Unit tests for the dataset tools offered to specialized agents."""

from __future__ import annotations

import json
from uuid import uuid4

import pyarrow as pa
from _agent_fakes import (
    FakeAuditLogger,
    FakeDatasetRepository,
    FakeDatasetStorage,
    FakeForecastRepository,
)

from quantix_api.application.interfaces.agent_graph import AgentRunContext
from quantix_api.application.use_cases.generate_forecast import GenerateForecastUseCase
from quantix_api.domain.entities.dataset import (
    Dataset,
    DatasetColumn,
    DatasetColumnType,
    DatasetStatus,
)
from quantix_api.infrastructure.agents.tools import build_dataset_tools


def _context(
    *, dataset: Dataset | None, storage: FakeDatasetStorage | None = None
) -> AgentRunContext:
    resolved_storage = storage or FakeDatasetStorage()
    tenant_id = dataset.tenant_id if dataset is not None else uuid4()
    dataset_repo = FakeDatasetRepository(
        datasets={dataset.id: dataset} if dataset is not None else {}
    )
    return AgentRunContext(
        tenant_id=tenant_id,
        actor_user_id=uuid4(),
        conversation_id=uuid4(),
        dataset=dataset,
        dataset_repo=None,
        dataset_storage=resolved_storage,
        data_source_repo=None,
        connector_factory=None,
        cipher=None,
        sync_dataset_use_case=None,
        discover_use_case=None,
        generate_forecast_use_case=GenerateForecastUseCase(
            dataset_repo=dataset_repo,
            dataset_storage=resolved_storage,
            forecast_repo=FakeForecastRepository(),
            audit_logger=FakeAuditLogger(),
        ),
    )


def _dataset(*, storage_uri: str | None) -> Dataset:
    return Dataset(
        tenant_id=uuid4(),
        data_source_id=uuid4(),
        name="orders",
        table_identifier="orders",
        storage_uri=storage_uri,
        status=DatasetStatus.READY if storage_uri is not None else DatasetStatus.PENDING,
        schema=[
            DatasetColumn(name="id", data_type=DatasetColumnType.INTEGER),
            DatasetColumn(name="amount", data_type=DatasetColumnType.FLOAT),
        ],
        row_count=3,
    )


class TestBuildDatasetTools:
    def test_no_dataset_returns_no_tools(self) -> None:
        assert build_dataset_tools(_context(dataset=None)) == []

    def test_dataset_without_storage_uri_returns_no_tools(self) -> None:
        assert build_dataset_tools(_context(dataset=_dataset(storage_uri=None))) == []

    def test_ready_dataset_returns_all_four_tools(self) -> None:
        tools = build_dataset_tools(_context(dataset=_dataset(storage_uri="uri")))
        assert {t.spec.name for t in tools} == {
            "get_dataset_schema",
            "query_dataset",
            "run_python_analysis",
            "forecast_series",
        }


class TestSchemaTool:
    async def test_returns_column_names_and_types(self) -> None:
        dataset = _dataset(storage_uri="uri")
        tools = build_dataset_tools(_context(dataset=dataset))
        schema_tool = next(t for t in tools if t.spec.name == "get_dataset_schema")

        result = json.loads(await schema_tool.call({}))

        assert result["row_count"] == 3
        assert {c["name"] for c in result["columns"]} == {"id", "amount"}


class TestQueryTool:
    async def test_runs_against_dataset_storage(self) -> None:
        storage = FakeDatasetStorage()
        storage.put("uri", pa.table({"id": [1, 2, 3]}))
        dataset = _dataset(storage_uri="uri")
        tools = build_dataset_tools(_context(dataset=dataset, storage=storage))
        query_tool = next(t for t in tools if t.spec.name == "query_dataset")

        result = json.loads(await query_tool.call({"sql": "SELECT * FROM dataset"}))

        assert result["row_count"] == 3

    async def test_storage_failure_is_returned_as_text_not_raised(self) -> None:
        class BrokenStorage(FakeDatasetStorage):
            def query(self, *, storage_uri, sql, limit=1000):
                raise RuntimeError("boom")

        dataset = _dataset(storage_uri="uri")
        tools = build_dataset_tools(_context(dataset=dataset, storage=BrokenStorage()))
        query_tool = next(t for t in tools if t.spec.name == "query_dataset")

        result = await query_tool.call({"sql": "SELECT 1"})

        assert "Query failed" in result


class TestPythonTool:
    async def test_computes_a_result_variable(self) -> None:
        storage = FakeDatasetStorage()
        storage.put("uri", pa.table({"id": [1, 2, 3]}))
        dataset = _dataset(storage_uri="uri")
        tools = build_dataset_tools(_context(dataset=dataset, storage=storage))
        python_tool = next(t for t in tools if t.spec.name == "run_python_analysis")

        result = await python_tool.call({"code": "result = int(df['id'].sum())"})

        assert "result = 6" in result

    async def test_print_output_is_captured(self) -> None:
        storage = FakeDatasetStorage()
        storage.put("uri", pa.table({"id": [1, 2]}))
        dataset = _dataset(storage_uri="uri")
        tools = build_dataset_tools(_context(dataset=dataset, storage=storage))
        python_tool = next(t for t in tools if t.spec.name == "run_python_analysis")

        result = await python_tool.call({"code": "print('hello from the sandbox')"})

        assert "hello from the sandbox" in result

    async def test_restricted_builtins_block_import(self) -> None:
        storage = FakeDatasetStorage()
        storage.put("uri", pa.table({"id": [1]}))
        dataset = _dataset(storage_uri="uri")
        tools = build_dataset_tools(_context(dataset=dataset, storage=storage))
        python_tool = next(t for t in tools if t.spec.name == "run_python_analysis")

        result = await python_tool.call({"code": "import os\nresult = os.getcwd()"})

        assert "Execution failed" in result


class TestForecastTool:
    async def test_short_series_falls_back_to_linear_trend_and_persists(self) -> None:
        storage = FakeDatasetStorage()
        storage.put("uri", pa.table({"value": [10.0, 20.0, 30.0, 40.0]}))
        dataset = _dataset(storage_uri="uri")
        tools = build_dataset_tools(_context(dataset=dataset, storage=storage))
        forecast_tool = next(t for t in tools if t.spec.name == "forecast_series")

        result = json.loads(await forecast_tool.call({"column": "value", "periods": 2}))

        assert result["method"] == "linear_trend"
        assert result["historical_points"] == 4
        assert result["forecast_id"]
        assert len(result["forecast"]) == 2
        # Trend is +10/period, so the next two points should continue upward.
        assert result["forecast"][0]["value"] > 40
        assert result["forecast"][1]["value"] > result["forecast"][0]["value"]
        # A real (if heuristic) interval, not just a bare point forecast.
        assert (
            result["forecast"][0]["lower"]
            <= result["forecast"][0]["value"]
            <= result["forecast"][0]["upper"]
        )

    async def test_long_series_uses_holt_winters(self) -> None:
        storage = FakeDatasetStorage()
        values = [float(50 + 2 * i) for i in range(20)]
        storage.put("uri", pa.table({"value": values}))
        dataset = _dataset(storage_uri="uri")
        tools = build_dataset_tools(_context(dataset=dataset, storage=storage))
        forecast_tool = next(t for t in tools if t.spec.name == "forecast_series")

        result = json.loads(await forecast_tool.call({"column": "value", "periods": 3}))

        assert result["method"] == "holt_winters"
        assert len(result["forecast"]) == 3
        assert result["forecast"][0]["lower"] < result["forecast"][0]["upper"]

    async def test_too_few_points_is_reported_not_raised(self) -> None:
        storage = FakeDatasetStorage()
        storage.put("uri", pa.table({"value": [10.0]}))
        dataset = _dataset(storage_uri="uri")
        tools = build_dataset_tools(_context(dataset=dataset, storage=storage))
        forecast_tool = next(t for t in tools if t.spec.name == "forecast_series")

        result = await forecast_tool.call({"column": "value", "periods": 2})

        assert "at least" in result

    async def test_unknown_column_is_reported_not_raised(self) -> None:
        storage = FakeDatasetStorage()
        storage.put("uri", pa.table({"value": [10.0, 20.0, 30.0]}))
        dataset = _dataset(storage_uri="uri")
        tools = build_dataset_tools(_context(dataset=dataset, storage=storage))
        forecast_tool = next(t for t in tools if t.spec.name == "forecast_series")

        result = await forecast_tool.call({"column": "does_not_exist", "periods": 2})

        assert "was not found" in result
