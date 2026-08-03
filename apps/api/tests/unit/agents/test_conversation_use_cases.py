"""Unit tests for StartConversationUseCase and SendMessageUseCase,
against fakes (including a scripted FakeAgentGraph) — no real LLM or
LangGraph execution.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from _agent_fakes import (
    FakeAgentGraph,
    FakeAgentRunRepository,
    FakeAuditLogger,
    FakeConversationRepository,
    FakeDatasetStorage,
    FakeMessageRepository,
)

from quantix_api.application.interfaces.agent_graph import AgentRunResult, AgentState, AgentTurn
from quantix_api.application.use_cases.send_message import SendMessageUseCase
from quantix_api.application.use_cases.start_conversation import StartConversationUseCase
from quantix_api.domain.entities.agent_run import AgentRunStatus, AgentType
from quantix_api.domain.entities.conversation import Conversation, ConversationStatus
from quantix_api.domain.exceptions.agents import ConversationNotActiveError
from quantix_api.domain.exceptions.base import EntityNotFoundError


class TestStartConversationUseCase:
    async def test_creates_a_conversation_and_records_audit(self) -> None:
        conversation_repo = FakeConversationRepository()
        audit_logger = FakeAuditLogger()
        use_case = StartConversationUseCase(
            conversation_repo=conversation_repo, dataset_repo=None, audit_logger=audit_logger
        )
        tenant_id, user_id = uuid4(), uuid4()

        conversation = await use_case.execute(
            tenant_id=tenant_id, actor_user_id=user_id, title="Q3 sales review"
        )

        assert conversation.status is ConversationStatus.ACTIVE
        assert conversation.id in conversation_repo.store
        assert any(r["action"].value == "conversation.started" for r in audit_logger.records)

    async def test_unknown_dataset_raises_not_found(self) -> None:
        class _EmptyDatasetRepo:
            async def get_by_id(self, entity_id):  # noqa: ANN001, ANN201
                return None

        use_case = StartConversationUseCase(
            conversation_repo=FakeConversationRepository(),
            dataset_repo=_EmptyDatasetRepo(),
            audit_logger=FakeAuditLogger(),
        )

        with pytest.raises(EntityNotFoundError):
            await use_case.execute(
                tenant_id=uuid4(), actor_user_id=uuid4(), title="x", dataset_id=uuid4()
            )


class TestSendMessageUseCase:
    def _build(self, *, final_state: AgentState):
        conversation_repo = FakeConversationRepository()
        message_repo = FakeMessageRepository()
        agent_run_repo = FakeAgentRunRepository()
        audit_logger = FakeAuditLogger()
        agent_graph = FakeAgentGraph(final_state=final_state)
        use_case = SendMessageUseCase(
            conversation_repo=conversation_repo,
            message_repo=message_repo,
            agent_run_repo=agent_run_repo,
            dataset_repo=None,
            dataset_storage=FakeDatasetStorage(),
            data_source_repo=None,
            connector_factory=None,
            cipher=None,
            sync_dataset_use_case=None,
            discover_use_case=None,
            agent_graph=agent_graph,
            audit_logger=audit_logger,
        )
        return use_case, conversation_repo, message_repo, agent_run_repo, audit_logger, agent_graph

    async def test_happy_path_persists_message_and_agent_runs(self) -> None:
        conversation_id = uuid4()
        final_state = AgentState(
            conversation_id=conversation_id,
            tenant_id=uuid4(),
            history=[],
            final_response="There are 42 rows.",
            finished=True,
            agent_runs=[
                AgentRunResult(agent_type=AgentType.SUPERVISOR, status=AgentRunStatus.SUCCEEDED),
                AgentRunResult(
                    agent_type=AgentType.SQL_GENERATION,
                    status=AgentRunStatus.SUCCEEDED,
                    output_summary="42",
                ),
            ],
        )
        use_case, conversation_repo, message_repo, agent_run_repo, audit_logger, agent_graph = self._build(
            final_state=final_state
        )
        tenant_id = uuid4()
        conversation = await conversation_repo.add(
            Conversation(id=conversation_id, tenant_id=tenant_id, title="t", created_by_user_id=uuid4())
        )

        result = await use_case.execute(
            tenant_id=tenant_id,
            conversation_id=conversation.id,
            actor_user_id=uuid4(),
            content="How many rows are there?",
        )

        assert result.message.content == "There are 42 rows."
        # Only the SQL_GENERATION agent produced user-facing output — the
        # supervisor itself is excluded from "who answered".
        assert result.message.agent_type is AgentType.SQL_GENERATION
        assert len(result.agent_runs) == 2
        assert len(message_repo.store) == 2  # user turn + assistant turn
        assert any(r["action"].value == "agent_turn.completed" for r in audit_logger.records)
        # The graph was invoked with the user turn already in history.
        run_call = agent_graph.run_calls[0]
        assert any(t.content == "How many rows are there?" for t in run_call["state"].history)

    async def test_unknown_conversation_raises_not_found(self) -> None:
        use_case, *_rest = self._build(final_state=AgentState(conversation_id=uuid4(), tenant_id=uuid4(), history=[]))

        with pytest.raises(EntityNotFoundError):
            await use_case.execute(
                tenant_id=uuid4(), conversation_id=uuid4(), actor_user_id=uuid4(), content="hi"
            )

    async def test_archived_conversation_rejects_new_messages(self) -> None:
        use_case, conversation_repo, *_rest = self._build(
            final_state=AgentState(conversation_id=uuid4(), tenant_id=uuid4(), history=[])
        )
        tenant_id = uuid4()
        conversation = Conversation(tenant_id=tenant_id, title="t", created_by_user_id=uuid4())
        conversation.archive()
        await conversation_repo.add(conversation)

        with pytest.raises(ConversationNotActiveError):
            await use_case.execute(
                tenant_id=tenant_id, conversation_id=conversation.id, actor_user_id=uuid4(), content="hi"
            )

    async def test_all_agents_failing_records_agent_turn_failed(self) -> None:
        conversation_id = uuid4()
        final_state = AgentState(
            conversation_id=conversation_id,
            tenant_id=uuid4(),
            history=[],
            final_response="Something went wrong.",
            finished=True,
            agent_runs=[
                AgentRunResult(
                    agent_type=AgentType.SUPERVISOR, status=AgentRunStatus.FAILED, error_message="boom"
                )
            ],
        )
        use_case, conversation_repo, _message_repo, _agent_run_repo, audit_logger, _graph = self._build(
            final_state=final_state
        )
        tenant_id = uuid4()
        conversation = await conversation_repo.add(
            Conversation(id=conversation_id, tenant_id=tenant_id, title="t", created_by_user_id=uuid4())
        )

        await use_case.execute(
            tenant_id=tenant_id, conversation_id=conversation.id, actor_user_id=uuid4(), content="hi"
        )

        assert any(r["action"].value == "agent_turn.failed" for r in audit_logger.records)
