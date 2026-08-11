"""Send a user message into a Conversation and run it through the agent
graph — the single entry point that turns "user typed something" into
"supervisor routed to zero or more specialized agents, an assistant
Message got persisted, and every agent invocation is recorded as an
AgentRun for observability."

Deliberately synchronous end-to-end (no Celery hop): a conversation turn
is expected to complete within an HTTP request/response cycle, unlike
milestone 3's large dataset syncs. See ADR-0004 for why, and for the
streaming-response follow-up this rules out for now.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from quantix_api.application.interfaces.agent_graph import (
    AgentGraph,
    AgentRunContext,
    AgentState,
    AgentTurn,
)
from quantix_api.application.interfaces.audit_logger import AuditLogger
from quantix_api.application.interfaces.connector_factory import ConnectorFactory
from quantix_api.application.interfaces.credential_cipher import CredentialCipher
from quantix_api.application.interfaces.dataset_storage import DatasetStorage
from quantix_api.application.use_cases.discover_data_source_schema import (
    DiscoverDataSourceSchemaUseCase,
)
from quantix_api.application.use_cases.generate_forecast import GenerateForecastUseCase
from quantix_api.application.use_cases.sync_dataset import SyncDatasetUseCase
from quantix_api.domain.entities.agent_run import AgentRun, AgentRunStatus, AgentType
from quantix_api.domain.entities.audit_log import AuditAction
from quantix_api.domain.entities.conversation import ConversationStatus
from quantix_api.domain.entities.message import Message, MessageRole
from quantix_api.domain.exceptions.agents import ConversationNotActiveError
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.domain.repositories.agent_run_repository import AgentRunRepository
from quantix_api.domain.repositories.conversation_repository import ConversationRepository
from quantix_api.domain.repositories.data_source_repository import DataSourceRepository
from quantix_api.domain.repositories.dataset_repository import DatasetRepository
from quantix_api.domain.repositories.message_repository import MessageRepository


@dataclass(frozen=True, slots=True)
class SendMessageResult:
    message: Message
    agent_runs: list[AgentRun]


class SendMessageUseCase:
    def __init__(
        self,
        *,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
        agent_run_repo: AgentRunRepository,
        dataset_repo: DatasetRepository,
        dataset_storage: DatasetStorage,
        data_source_repo: DataSourceRepository,
        connector_factory: ConnectorFactory,
        cipher: CredentialCipher,
        sync_dataset_use_case: SyncDatasetUseCase,
        discover_use_case: DiscoverDataSourceSchemaUseCase,
        generate_forecast_use_case: GenerateForecastUseCase,
        agent_graph: AgentGraph,
        audit_logger: AuditLogger,
        max_iterations: int = 6,
    ) -> None:
        self._conversation_repo = conversation_repo
        self._message_repo = message_repo
        self._agent_run_repo = agent_run_repo
        self._dataset_repo = dataset_repo
        self._dataset_storage = dataset_storage
        self._data_source_repo = data_source_repo
        self._connector_factory = connector_factory
        self._cipher = cipher
        self._sync_dataset_use_case = sync_dataset_use_case
        self._discover_use_case = discover_use_case
        self._generate_forecast_use_case = generate_forecast_use_case
        self._agent_graph = agent_graph
        self._audit_logger = audit_logger
        self._max_iterations = max_iterations

    async def execute(
        self, *, tenant_id: UUID, conversation_id: UUID, actor_user_id: UUID, content: str
    ) -> SendMessageResult:
        conversation = await self._conversation_repo.get_by_id(conversation_id)
        if conversation is None or conversation.tenant_id != tenant_id:
            raise EntityNotFoundError("Conversation", conversation_id)
        if conversation.status is not ConversationStatus.ACTIVE:
            raise ConversationNotActiveError(conversation_id)

        user_message = await self._message_repo.add(
            Message(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content=content,
            )
        )

        history = await self._message_repo.list_for_conversation(conversation_id)
        turns = [
            AgentTurn(role=message.role.value, content=message.content)
            for message in history
            if message.role in (MessageRole.USER, MessageRole.ASSISTANT)
        ]

        dataset = None
        if conversation.dataset_id is not None:
            dataset = await self._dataset_repo.get_by_id(conversation.dataset_id)

        context = AgentRunContext(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            conversation_id=conversation_id,
            dataset=dataset,
            dataset_repo=self._dataset_repo,
            dataset_storage=self._dataset_storage,
            data_source_repo=self._data_source_repo,
            connector_factory=self._connector_factory,
            cipher=self._cipher,
            sync_dataset_use_case=self._sync_dataset_use_case,
            discover_use_case=self._discover_use_case,
            generate_forecast_use_case=self._generate_forecast_use_case,
            max_iterations=self._max_iterations,
        )
        initial_state = AgentState(
            conversation_id=conversation_id, tenant_id=tenant_id, history=turns
        )

        final_state = await self._agent_graph.run(state=initial_state, context=context)

        specialized_runs = [r for r in final_state.agent_runs if r.agent_type is not AgentType.SUPERVISOR]
        responding_agent = specialized_runs[-1].agent_type if specialized_runs else None

        assistant_message = await self._message_repo.add(
            Message(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content=final_state.final_response or "I wasn't able to produce a response.",
                agent_type=responding_agent,
            )
        )

        persisted_runs: list[AgentRun] = []
        for run_result in final_state.agent_runs:
            agent_run = await self._agent_run_repo.add(
                AgentRun(
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    message_id=assistant_message.id,
                    agent_type=run_result.agent_type,
                    status=run_result.status,
                    output_summary=run_result.output_summary,
                    tool_calls=run_result.tool_calls,
                    prompt_tokens=run_result.prompt_tokens,
                    completion_tokens=run_result.completion_tokens,
                    latency_ms=run_result.latency_ms,
                    error_message=run_result.error_message,
                )
            )
            persisted_runs.append(agent_run)

        any_failed = any(r.status is AgentRunStatus.FAILED for r in final_state.agent_runs)
        await self._audit_logger.record(
            action=AuditAction.AGENT_TURN_FAILED if any_failed else AuditAction.AGENT_TURN_COMPLETED,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            resource_type="conversation",
            resource_id=str(conversation_id),
            metadata={
                "agents_invoked": [r.agent_type.value for r in final_state.agent_runs],
                "user_message_id": str(user_message.id),
                "assistant_message_id": str(assistant_message.id),
            },
        )

        return SendMessageResult(message=assistant_message, agent_runs=persisted_runs)
