"""Unit tests for SupervisorNode — the routing decision at the center of
the agent graph.
"""

from __future__ import annotations

from uuid import uuid4

from _agent_fakes import FakeDatasetStorage, FakeLLMClient

from quantix_api.application.interfaces.agent_graph import AgentRunContext, AgentState, AgentTurn
from quantix_api.application.interfaces.llm_client import LLMResponse, LLMToolCall, LLMUsage
from quantix_api.domain.entities.agent_run import AgentRunStatus, AgentType
from quantix_api.infrastructure.agents.supervisor import SupervisorNode


def _state(*, iterations: int = 0) -> AgentState:
    return AgentState(
        conversation_id=uuid4(),
        tenant_id=uuid4(),
        history=[AgentTurn(role="user", content="How many rows are in this dataset?")],
        iterations=iterations,
    )


def _context(*, max_iterations: int = 6) -> AgentRunContext:
    return AgentRunContext(
        tenant_id=uuid4(),
        actor_user_id=uuid4(),
        conversation_id=uuid4(),
        dataset=None,
        dataset_repo=None,
        dataset_storage=FakeDatasetStorage(),
        data_source_repo=None,
        connector_factory=None,
        cipher=None,
        sync_dataset_use_case=None,
        discover_use_case=None,
        generate_forecast_use_case=None,
        max_iterations=max_iterations,
    )


class TestSupervisorNode:
    async def test_routes_to_a_valid_agent(self) -> None:
        llm = FakeLLMClient(
            [
                LLMResponse(
                    text=None,
                    tool_calls=[
                        LLMToolCall(
                            id="1",
                            name="route_to_agent",
                            arguments={"agent_type": "sql_generation", "instructions": "count rows"},
                        )
                    ],
                    usage=LLMUsage(4, 4),
                )
            ]
        )
        supervisor = SupervisorNode(llm_client=llm)

        decision = await supervisor.decide(state=_state(), context=_context())

        assert decision.finished is False
        assert decision.next_agent is AgentType.SQL_GENERATION
        assert decision.run_result.status is AgentRunStatus.SUCCEEDED
        assert decision.run_result.agent_type is AgentType.SUPERVISOR

    async def test_finish_tool_ends_the_turn(self) -> None:
        llm = FakeLLMClient(
            [
                LLMResponse(
                    text=None,
                    tool_calls=[
                        LLMToolCall(id="1", name="finish", arguments={"response": "There are 42 rows."})
                    ],
                    usage=LLMUsage(2, 2),
                )
            ]
        )
        supervisor = SupervisorNode(llm_client=llm)

        decision = await supervisor.decide(state=_state(), context=_context())

        assert decision.finished is True
        assert decision.next_agent is None
        assert decision.final_response == "There are 42 rows."

    async def test_unknown_agent_type_falls_back_to_a_graceful_finish(self) -> None:
        llm = FakeLLMClient(
            [
                LLMResponse(
                    text=None,
                    tool_calls=[LLMToolCall(id="1", name="route_to_agent", arguments={"agent_type": "nonsense"})],
                    usage=LLMUsage(1, 1),
                )
            ]
        )
        supervisor = SupervisorNode(llm_client=llm)

        decision = await supervisor.decide(state=_state(), context=_context())

        assert decision.finished is True
        assert decision.run_result.status is AgentRunStatus.FAILED
        assert decision.final_response is not None

    async def test_iteration_limit_forces_finish_without_calling_the_llm(self) -> None:
        llm = FakeLLMClient([])  # would raise "exhausted" if the LLM were called at all
        supervisor = SupervisorNode(llm_client=llm)

        decision = await supervisor.decide(
            state=_state(iterations=6), context=_context(max_iterations=6)
        )

        assert decision.finished is True
        assert decision.next_agent is None
        assert llm.calls == []

    async def test_llm_failure_ends_the_turn_gracefully(self) -> None:
        llm = FakeLLMClient([RuntimeError("provider down")])
        supervisor = SupervisorNode(llm_client=llm)

        decision = await supervisor.decide(state=_state(), context=_context())

        assert decision.finished is True
        assert decision.run_result.status is AgentRunStatus.FAILED
        assert "provider down" in decision.run_result.error_message

    async def test_no_tool_call_falls_back_to_plain_text_finish(self) -> None:
        llm = FakeLLMClient([LLMResponse(text="I'm not sure what you mean.", usage=LLMUsage(1, 1))])
        supervisor = SupervisorNode(llm_client=llm)

        decision = await supervisor.decide(state=_state(), context=_context())

        assert decision.finished is True
        assert decision.final_response == "I'm not sure what you mean."
