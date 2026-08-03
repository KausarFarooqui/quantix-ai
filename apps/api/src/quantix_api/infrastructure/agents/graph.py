"""Assembles the LangGraph state machine: a supervisor node that routes
to zero or more specialist nodes and loops back to itself, until it calls
``finish``. Also home to ``LangGraphAgentGraph``, the concrete
implementation of ``application.interfaces.agent_graph.AgentGraph``.

**Dependency injection into nodes.** The compiled graph is a process-wide
singleton (built once in ``core.container``, since compiling a
``StateGraph`` isn't free and every node closure here only captures the
stateless ``LLMClient``). Request-scoped dependencies — dataset storage,
repositories, other use cases — can't be captured in a node closure the
same way, so they're threaded through LangGraph's own mechanism for this:
a ``RunnableConfig``'s ``configurable`` dict, supplied at
``ainvoke()`` time and read back out inside each node via its `config`
argument. This is the idiomatic LangGraph pattern for request-scoped
context in an otherwise-singleton graph — see ADR-0004.

**State.** ``GraphState`` (a ``TypedDict``, as LangGraph's ``StateGraph``
expects) is an in-process mirror of ``application.interfaces.agent_graph
.AgentState`` — the two are kept in lockstep by ``_to_agent_state``/
``LangGraphAgentGraph.run``'s conversion at the boundary, so nothing in
``application`` needs to know LangGraph's state shape exists. Since this
graph never fans out to run two nodes concurrently (supervisor and
specialists strictly alternate), every node reads and returns the full
value of any list/dict field it touches rather than relying on LangGraph
reducers — simpler, and correct for this graph's shape.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from langgraph.graph import END, START, StateGraph

if TYPE_CHECKING:
    # Import path kept behind TYPE_CHECKING: it has moved between minor
    # LangGraph releases, and nothing at runtime needs the concrete type —
    # `build_agent_graph`'s return value and `LangGraphAgentGraph`'s
    # constructor parameter are only ever used structurally (`.ainvoke()`).
    from langgraph.graph.state import CompiledStateGraph

from quantix_api.application.interfaces.agent_graph import (
    AgentGraph,
    AgentRunContext,
    AgentRunResult,
    AgentState,
    AgentTurn,
)
from quantix_api.application.interfaces.llm_client import LLMClient
from quantix_api.domain.entities.agent_run import AgentType
from quantix_api.infrastructure.agents.automl_agent import AutoMLAgentNode
from quantix_api.infrastructure.agents.configs import AGENT_CONFIGS, ROUTING_DESCRIPTIONS
from quantix_api.infrastructure.agents.ingestion_agent import DataIngestionAgentNode
from quantix_api.infrastructure.agents.prompted_agent import PromptedAgentNode
from quantix_api.infrastructure.agents.supervisor import SupervisorNode


class GraphState(TypedDict):
    conversation_id: Any
    tenant_id: Any
    history: list[AgentTurn]
    agent_outputs: dict[str, Any]
    agent_runs: list[AgentRunResult]
    next_agent: AgentType | None
    finished: bool
    final_response: str | None
    iterations: int


def _to_agent_state(state: GraphState) -> AgentState:
    return AgentState(
        conversation_id=state["conversation_id"],
        tenant_id=state["tenant_id"],
        history=state["history"],
        agent_outputs=state["agent_outputs"],
        agent_runs=state["agent_runs"],
        next_agent=state["next_agent"],
        finished=state["finished"],
        final_response=state["final_response"],
        iterations=state["iterations"],
    )


def build_agent_graph(*, llm_client: LLMClient, max_tool_iterations: int = 5) -> CompiledStateGraph:
    """Build and compile the graph once — called a single time by
    ``core.container.get_container()``.
    """
    supervisor = SupervisorNode(llm_client=llm_client)
    automl_node = AutoMLAgentNode(llm_client=llm_client)
    ingestion_node = DataIngestionAgentNode()
    prompted_nodes = {
        agent_type: PromptedAgentNode(
            config=config, llm_client=llm_client, max_tool_iterations=max_tool_iterations
        )
        for agent_type, config in AGENT_CONFIGS.items()
    }

    graph: StateGraph = StateGraph(GraphState)

    async def supervisor_node(state: GraphState, config: dict) -> dict:
        context: AgentRunContext = config["configurable"]["context"]
        decision = await supervisor.decide(state=_to_agent_state(state), context=context)
        updates: dict[str, Any] = {
            "agent_runs": [*state["agent_runs"], decision.run_result],
            "iterations": state["iterations"] + 1,
            "next_agent": decision.next_agent,
            "finished": decision.finished,
        }
        if decision.final_response is not None:
            updates["final_response"] = decision.final_response
        return updates

    def make_specialist_node(agent_type: AgentType, node_impl: Any) -> Any:
        async def _node(state: GraphState, config: dict) -> dict:
            context: AgentRunContext = config["configurable"]["context"]
            result = await node_impl.run(state=_to_agent_state(state), context=context)
            return {
                "agent_runs": [*state["agent_runs"], result],
                "agent_outputs": {**state["agent_outputs"], agent_type.value: result.output_summary},
            }

        return _node

    graph.add_node("supervisor", supervisor_node)
    graph.add_node(
        AgentType.DATA_INGESTION.value,
        make_specialist_node(AgentType.DATA_INGESTION, ingestion_node),
    )
    graph.add_node(AgentType.AUTOML.value, make_specialist_node(AgentType.AUTOML, automl_node))
    for agent_type, node in prompted_nodes.items():
        graph.add_node(agent_type.value, make_specialist_node(agent_type, node))

    graph.add_edge(START, "supervisor")

    def route_from_supervisor(state: GraphState) -> str:
        if state["finished"] or state["next_agent"] is None:
            return END
        return state["next_agent"].value

    routing_map = {agent_type.value: agent_type.value for agent_type in ROUTING_DESCRIPTIONS}
    routing_map[END] = END
    graph.add_conditional_edges("supervisor", route_from_supervisor, routing_map)

    for agent_type in ROUTING_DESCRIPTIONS:
        graph.add_edge(agent_type.value, "supervisor")

    return graph.compile()


class LangGraphAgentGraph(AgentGraph):
    """Adapter satisfying ``application.interfaces.agent_graph.AgentGraph``
    by driving a compiled LangGraph state machine.
    """

    def __init__(self, *, compiled_graph: CompiledStateGraph, max_iterations: int) -> None:
        self._compiled_graph = compiled_graph
        # A LangGraph "superstep" is one node execution; a full
        # supervisor<->specialist round trip is two, plus the initial
        # supervisor call — pad generously so the graph's own recursion
        # guard never fires before our `max_iterations` circuit breaker does.
        self._recursion_limit = max_iterations * 3 + 10

    async def run(self, *, state: AgentState, context: AgentRunContext) -> AgentState:
        initial: GraphState = {
            "conversation_id": state.conversation_id,
            "tenant_id": state.tenant_id,
            "history": state.history,
            "agent_outputs": state.agent_outputs,
            "agent_runs": state.agent_runs,
            "next_agent": state.next_agent,
            "finished": state.finished,
            "final_response": state.final_response,
            "iterations": state.iterations,
        }
        result = await self._compiled_graph.ainvoke(
            initial,
            config={
                "configurable": {"context": context},
                "recursion_limit": self._recursion_limit,
            },
        )
        return _to_agent_state(result)
