"""Port for the multi-agent orchestration graph — the boundary between
``SendMessageUseCase`` (which only knows "run the graph, get a response
back to persist") and the LangGraph-based implementation
(``infrastructure.agents.graph``), which owns supervisor routing, tool
loops, and every specialized agent's execution.

``AgentState`` is this port's data contract, analogous to how
``connector.py`` treats ``pyarrow.Table`` as the connector layer's lingua
franca (see ADR-0003) — a plain dataclass, not a LangGraph ``TypedDict``,
so this module stays free of a `langgraph` import. The LangGraph
implementation converts to/from its own internal state shape at the
boundary.

``AgentRunContext`` carries every request-scoped dependency an agent node
might need (dataset storage, connector factory, other use cases). LangGraph
nodes are process-wide singletons (the compiled graph is built once — see
ADR-0004), so request-scoped services can't be captured in a node
closure; they're threaded through via this context instead, passed at
invoke time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import UUID

from quantix_api.domain.entities.agent_run import AgentRunStatus, AgentType

if TYPE_CHECKING:
    from quantix_api.application.interfaces.connector_factory import ConnectorFactory
    from quantix_api.application.interfaces.credential_cipher import CredentialCipher
    from quantix_api.application.interfaces.dataset_storage import DatasetStorage
    from quantix_api.application.use_cases.discover_data_source_schema import (
        DiscoverDataSourceSchemaUseCase,
    )
    from quantix_api.application.use_cases.sync_dataset import SyncDatasetUseCase
    from quantix_api.domain.entities.dataset import Dataset
    from quantix_api.domain.repositories.data_source_repository import DataSourceRepository
    from quantix_api.domain.repositories.dataset_repository import DatasetRepository


@dataclass(frozen=True, slots=True)
class AgentTurn:
    """One turn of conversation history handed to the graph — a thin,
    LLM-agnostic projection of ``domain.entities.message.Message``.
    """

    role: str  # "user" | "assistant"
    content: str


@dataclass(slots=True)
class AgentRunResult:
    """What one agent node produced, collected by the graph and handed
    back so ``SendMessageUseCase`` can persist it as an ``AgentRun`` row
    without the graph needing to know about repositories.
    """

    agent_type: AgentType
    status: AgentRunStatus
    output_summary: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    error_message: str | None = None


@dataclass(slots=True)
class AgentState:
    """The graph's working state for one conversation turn."""

    conversation_id: UUID
    tenant_id: UUID
    history: list[AgentTurn]  # prior turns, oldest-first, ending with the new user turn
    agent_outputs: dict[str, Any] = field(default_factory=dict)  # keyed by AgentType.value
    agent_runs: list[AgentRunResult] = field(default_factory=list)
    next_agent: AgentType | None = None
    finished: bool = False
    final_response: str | None = None
    iterations: int = 0


@dataclass(slots=True)
class AgentRunContext:
    """Request-scoped dependencies threaded into the compiled graph at
    invoke time (see module docstring).
    """

    tenant_id: UUID
    actor_user_id: UUID
    dataset: Dataset | None
    dataset_repo: DatasetRepository
    dataset_storage: DatasetStorage
    data_source_repo: DataSourceRepository
    connector_factory: ConnectorFactory
    cipher: CredentialCipher
    sync_dataset_use_case: SyncDatasetUseCase
    discover_use_case: DiscoverDataSourceSchemaUseCase
    max_iterations: int = 6


class AgentGraph:
    """Structural port — implemented by
    ``infrastructure.agents.adapter.LangGraphAgentGraph``. A plain class
    (not ``typing.Protocol``) since callers always receive a concrete
    instance from the container rather than duck-typing against it; kept
    here for the same reason every other cross-layer contract lives in
    ``application.interfaces``.
    """

    async def run(self, *, state: AgentState, context: AgentRunContext) -> AgentState:
        raise NotImplementedError
