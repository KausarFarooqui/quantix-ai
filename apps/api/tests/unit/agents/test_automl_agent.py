"""Unit tests for AutoMLAgentNode — real scikit-learn training against a
small synthetic dataset (fast enough for a unit test, large enough to
exercise cross-validation without a folds-vs-rows error).
"""

from __future__ import annotations

from uuid import uuid4

import pyarrow as pa
from _agent_fakes import FakeDatasetStorage, FakeLLMClient

from quantix_api.application.interfaces.agent_graph import AgentRunContext, AgentState, AgentTurn
from quantix_api.application.interfaces.llm_client import LLMResponse, LLMToolCall, LLMUsage
from quantix_api.domain.entities.agent_run import AgentRunStatus
from quantix_api.domain.entities.dataset import Dataset
from quantix_api.infrastructure.agents.automl_agent import AutoMLAgentNode


def _state(request: str) -> AgentState:
    return AgentState(
        conversation_id=uuid4(), tenant_id=uuid4(), history=[AgentTurn(role="user", content=request)]
    )


def _context(*, storage: FakeDatasetStorage, dataset: Dataset) -> AgentRunContext:
    return AgentRunContext(
        tenant_id=dataset.tenant_id,
        actor_user_id=uuid4(),
        dataset=dataset,
        dataset_repo=None,
        dataset_storage=storage,
        data_source_repo=None,
        connector_factory=None,
        cipher=None,
        sync_dataset_use_case=None,
        discover_use_case=None,
    )


def _column_tool_call(column: str) -> LLMResponse:
    return LLMResponse(
        text=None,
        tool_calls=[LLMToolCall(id="1", name="select_target_column", arguments={"column": column})],
        usage=LLMUsage(3, 3),
    )


class TestAutoMLAgentNode:
    async def test_trains_a_regression_model(self) -> None:
        rows = 30
        table = pa.table(
            {
                "feature": [float(i) for i in range(rows)],
                "target": [2.0 * i + 0.1 for i in range(rows)],  # 30 distinct values -> regression
            }
        )
        storage = FakeDatasetStorage()
        storage.put("uri", table)
        dataset = Dataset(
            tenant_id=uuid4(), data_source_id=uuid4(), name="d", table_identifier="t", storage_uri="uri"
        )
        llm = FakeLLMClient([_column_tool_call("target")])
        node = AutoMLAgentNode(llm_client=llm)

        result = await node.run(state=_state("predict target"), context=_context(storage=storage, dataset=dataset))

        assert result.status is AgentRunStatus.SUCCEEDED
        assert "regression" in result.output_summary
        assert "target" in result.output_summary
        assert "structured_result=" in result.output_summary

    async def test_trains_a_classification_model(self) -> None:
        rows = 20
        table = pa.table(
            {
                "feature": [float(i) for i in range(rows)],
                "label": ["A" if i % 2 == 0 else "B" for i in range(rows)],
            }
        )
        storage = FakeDatasetStorage()
        storage.put("uri", table)
        dataset = Dataset(
            tenant_id=uuid4(), data_source_id=uuid4(), name="d", table_identifier="t", storage_uri="uri"
        )
        llm = FakeLLMClient([_column_tool_call("label")])
        node = AutoMLAgentNode(llm_client=llm)

        result = await node.run(state=_state("what predicts label"), context=_context(storage=storage, dataset=dataset))

        assert result.status is AgentRunStatus.SUCCEEDED
        assert "classification" in result.output_summary

    async def test_no_dataset_attached_fails_gracefully(self) -> None:
        llm = FakeLLMClient([])
        node = AutoMLAgentNode(llm_client=llm)
        context = AgentRunContext(
            tenant_id=uuid4(),
            actor_user_id=uuid4(),
            dataset=None,
            dataset_repo=None,
            dataset_storage=FakeDatasetStorage(),
            data_source_repo=None,
            connector_factory=None,
            cipher=None,
            sync_dataset_use_case=None,
            discover_use_case=None,
        )

        result = await node.run(state=_state("predict something"), context=context)

        assert result.status is AgentRunStatus.FAILED
        assert "No dataset" in result.error_message

    async def test_llm_choosing_an_invalid_column_fails_gracefully(self) -> None:
        table = pa.table({"feature": [1.0, 2.0, 3.0]})
        storage = FakeDatasetStorage()
        storage.put("uri", table)
        dataset = Dataset(
            tenant_id=uuid4(), data_source_id=uuid4(), name="d", table_identifier="t", storage_uri="uri"
        )
        llm = FakeLLMClient([_column_tool_call("not_a_real_column")])
        node = AutoMLAgentNode(llm_client=llm)

        result = await node.run(state=_state("predict nonsense"), context=_context(storage=storage, dataset=dataset))

        assert result.status is AgentRunStatus.FAILED

    async def test_too_few_rows_fails_gracefully(self) -> None:
        table = pa.table({"feature": [1.0, 2.0], "target": [1.0, 2.0]})
        storage = FakeDatasetStorage()
        storage.put("uri", table)
        dataset = Dataset(
            tenant_id=uuid4(), data_source_id=uuid4(), name="d", table_identifier="t", storage_uri="uri"
        )
        llm = FakeLLMClient([_column_tool_call("target")])
        node = AutoMLAgentNode(llm_client=llm)

        result = await node.run(state=_state("predict target"), context=_context(storage=storage, dataset=dataset))

        assert result.status is AgentRunStatus.FAILED
        assert "too few" in result.error_message.lower()
