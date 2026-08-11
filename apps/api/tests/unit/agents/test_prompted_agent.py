"""Unit tests for PromptedAgentNode — the generic tool-calling loop used
by ten of the twelve agent types.
"""

from __future__ import annotations

from uuid import uuid4

import pyarrow as pa
from _agent_fakes import FakeDatasetStorage, FakeLLMClient

from quantix_api.application.interfaces.agent_graph import AgentRunContext, AgentState, AgentTurn
from quantix_api.application.interfaces.llm_client import LLMResponse, LLMToolCall, LLMUsage
from quantix_api.domain.entities.agent_run import AgentRunStatus, AgentType
from quantix_api.domain.entities.dataset import Dataset
from quantix_api.infrastructure.agents.configs import AgentConfig
from quantix_api.infrastructure.agents.prompted_agent import PromptedAgentNode

_CONFIG = AgentConfig(
    agent_type=AgentType.DATA_PROFILING,
    display_name="Data Profiling",
    routing_description="test",
    system_prompt="You are a test agent.",
)

_NO_TOOLS_CONFIG = AgentConfig(
    agent_type=AgentType.EXECUTIVE_REPORT,
    display_name="Executive Report",
    routing_description="test",
    system_prompt="You summarize.",
    uses_dataset_tools=False,
)


def _state(**agent_outputs: str) -> AgentState:
    return AgentState(
        conversation_id=uuid4(),
        tenant_id=uuid4(),
        history=[AgentTurn(role="user", content="Describe the dataset")],
        agent_outputs=agent_outputs,
    )


def _context(*, dataset: Dataset | None = None, storage: FakeDatasetStorage | None = None) -> AgentRunContext:
    return AgentRunContext(
        tenant_id=uuid4(),
        actor_user_id=uuid4(),
        conversation_id=uuid4(),
        dataset=dataset,
        dataset_repo=None,
        dataset_storage=storage or FakeDatasetStorage(),
        data_source_repo=None,
        connector_factory=None,
        cipher=None,
        sync_dataset_use_case=None,
        discover_use_case=None,
        generate_forecast_use_case=None,
    )


class TestPromptedAgentNode:
    async def test_plain_text_response_succeeds_without_tool_calls(self) -> None:
        llm = FakeLLMClient(
            [LLMResponse(text="This dataset has 3 columns.", usage=LLMUsage(10, 20))]
        )
        node = PromptedAgentNode(config=_CONFIG, llm_client=llm)

        result = await node.run(state=_state(), context=_context())

        assert result.status is AgentRunStatus.SUCCEEDED
        assert result.output_summary == "This dataset has 3 columns."
        assert result.prompt_tokens == 10
        assert result.completion_tokens == 20
        assert result.tool_calls == []

    async def test_executes_a_tool_call_then_returns_final_text(self) -> None:
        storage = FakeDatasetStorage()
        storage.put("uri", pa.table({"id": [1, 2, 3]}))
        dataset = Dataset(
            tenant_id=uuid4(), data_source_id=uuid4(), name="d", table_identifier="t", storage_uri="uri"
        )
        llm = FakeLLMClient(
            [
                LLMResponse(
                    text=None,
                    tool_calls=[LLMToolCall(id="call_1", name="get_dataset_schema", arguments={})],
                    usage=LLMUsage(5, 5),
                ),
                LLMResponse(text="The dataset has one column: id.", usage=LLMUsage(8, 8)),
            ]
        )
        node = PromptedAgentNode(config=_CONFIG, llm_client=llm)

        result = await node.run(state=_state(), context=_context(dataset=dataset, storage=storage))

        assert result.status is AgentRunStatus.SUCCEEDED
        assert result.output_summary == "The dataset has one column: id."
        assert result.tool_calls == [{"name": "get_dataset_schema", "arguments": {}}]
        assert result.prompt_tokens == 13
        assert result.completion_tokens == 13
        # Second LLM call must include the tool result as a "tool" turn.
        second_call_messages = llm.calls[1]["messages"]
        assert any(m.role == "tool" and m.tool_call_id == "call_1" for m in second_call_messages)

    async def test_llm_failure_is_a_failed_result_not_a_raised_exception(self) -> None:
        llm = FakeLLMClient([RuntimeError("provider is down")])
        node = PromptedAgentNode(config=_CONFIG, llm_client=llm)

        result = await node.run(state=_state(), context=_context())

        assert result.status is AgentRunStatus.FAILED
        assert "provider is down" in result.error_message

    async def test_agent_without_dataset_tools_never_offers_tools(self) -> None:
        dataset = Dataset(
            tenant_id=uuid4(), data_source_id=uuid4(), name="d", table_identifier="t", storage_uri="uri"
        )
        llm = FakeLLMClient([LLMResponse(text="Summary.", usage=LLMUsage(1, 1))])
        node = PromptedAgentNode(config=_NO_TOOLS_CONFIG, llm_client=llm)

        await node.run(state=_state(), context=_context(dataset=dataset))

        assert llm.calls[0]["tools"] is None

    async def test_loop_exhaustion_forces_a_final_tools_disabled_call(self) -> None:
        storage = FakeDatasetStorage()
        storage.put("uri", pa.table({"id": [1]}))
        dataset = Dataset(
            tenant_id=uuid4(), data_source_id=uuid4(), name="d", table_identifier="t", storage_uri="uri"
        )
        max_iterations = 2
        looping_response = LLMResponse(
            text=None,
            tool_calls=[LLMToolCall(id="c", name="get_dataset_schema", arguments={})],
            usage=LLMUsage(1, 1),
        )
        llm = FakeLLMClient(
            [looping_response, looping_response, LLMResponse(text="forced summary", usage=LLMUsage(1, 1))]
        )
        node = PromptedAgentNode(config=_CONFIG, llm_client=llm, max_tool_iterations=max_iterations)

        result = await node.run(state=_state(), context=_context(dataset=dataset, storage=storage))

        assert result.status is AgentRunStatus.SUCCEEDED
        assert result.output_summary == "forced summary"
        assert len(llm.calls) == max_iterations + 1
        assert llm.calls[-1]["tools"] is None

    async def test_prior_agent_outputs_are_injected_into_the_system_prompt(self) -> None:
        llm = FakeLLMClient([LLMResponse(text="ok", usage=LLMUsage(1, 1))])
        node = PromptedAgentNode(config=_CONFIG, llm_client=llm)

        await node.run(state=_state(sql_generation="SELECT 1"), context=_context())

        assert "SELECT 1" in llm.calls[0]["system"]
