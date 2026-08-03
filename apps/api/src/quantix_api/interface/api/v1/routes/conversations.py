"""Conversation and agent-turn endpoints — start a conversation, send a
message (runs the agent graph synchronously and returns the assistant's
reply plus every agent invoked), and list history.

Streaming the assistant's reply token-by-token (SSE) is a deliberate,
documented follow-up rather than what's built here — see ADR-0004.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from quantix_api.domain.entities.agent_run import AgentRun
from quantix_api.domain.entities.conversation import Conversation
from quantix_api.domain.entities.message import Message
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.interface.api.v1.dependencies.agent_use_cases import (
    SendMessageUseCaseDep,
    StartConversationUseCaseDep,
)
from quantix_api.interface.api.v1.dependencies.auth import CurrentUser
from quantix_api.interface.api.v1.dependencies.repositories import AgentRunRepo, ConversationRepo, MessageRepo
from quantix_api.interface.api.v1.schemas.agents import (
    AgentRunResponse,
    ConversationCreateRequest,
    ConversationResponse,
    MessageCreateRequest,
    MessageResponse,
    SendMessageResponse,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _to_conversation_response(conversation: Conversation) -> ConversationResponse:
    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        dataset_id=conversation.dataset_id,
        status=conversation.status,
        created_at=conversation.created_at,
    )


def _to_message_response(message: Message) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        agent_type=message.agent_type,
        created_at=message.created_at,
    )


def _to_agent_run_response(agent_run: AgentRun) -> AgentRunResponse:
    return AgentRunResponse(
        id=agent_run.id,
        agent_type=agent_run.agent_type,
        status=agent_run.status,
        output_summary=agent_run.output_summary,
        tool_calls=agent_run.tool_calls,
        prompt_tokens=agent_run.prompt_tokens,
        completion_tokens=agent_run.completion_tokens,
        latency_ms=agent_run.latency_ms,
        error_message=agent_run.error_message,
        created_at=agent_run.created_at,
    )


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new conversation, optionally scoped to a dataset",
)
async def start_conversation(
    body: ConversationCreateRequest, use_case: StartConversationUseCaseDep, current_user: CurrentUser
) -> ConversationResponse:
    conversation = await use_case.execute(
        tenant_id=current_user.tenant_id,
        actor_user_id=current_user.id,
        title=body.title,
        dataset_id=body.dataset_id,
    )
    return _to_conversation_response(conversation)


@router.get("", response_model=list[ConversationResponse], summary="List conversations for the current tenant")
async def list_conversations(
    conversation_repo: ConversationRepo, current_user: CurrentUser
) -> list[ConversationResponse]:
    conversations = await conversation_repo.list_for_tenant(current_user.tenant_id)
    return [_to_conversation_response(c) for c in conversations]


@router.get("/{conversation_id}", response_model=ConversationResponse, summary="Get a single conversation")
async def get_conversation(
    conversation_id: UUID, conversation_repo: ConversationRepo, current_user: CurrentUser
) -> ConversationResponse:
    conversation = await conversation_repo.get_by_id(conversation_id)
    if conversation is None or conversation.tenant_id != current_user.tenant_id:
        raise EntityNotFoundError("Conversation", conversation_id)
    return _to_conversation_response(conversation)


@router.get(
    "/{conversation_id}/messages",
    response_model=list[MessageResponse],
    summary="List messages in a conversation, oldest first",
)
async def list_messages(
    conversation_id: UUID,
    conversation_repo: ConversationRepo,
    message_repo: MessageRepo,
    current_user: CurrentUser,
) -> list[MessageResponse]:
    conversation = await conversation_repo.get_by_id(conversation_id)
    if conversation is None or conversation.tenant_id != current_user.tenant_id:
        raise EntityNotFoundError("Conversation", conversation_id)
    messages = await message_repo.list_for_conversation(conversation_id)
    return [_to_message_response(m) for m in messages]


@router.post(
    "/{conversation_id}/messages",
    response_model=SendMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a message and run it through the agent graph",
)
async def send_message(
    conversation_id: UUID,
    body: MessageCreateRequest,
    use_case: SendMessageUseCaseDep,
    current_user: CurrentUser,
) -> SendMessageResponse:
    result = await use_case.execute(
        tenant_id=current_user.tenant_id,
        conversation_id=conversation_id,
        actor_user_id=current_user.id,
        content=body.content,
    )
    return SendMessageResponse(
        message=_to_message_response(result.message),
        agent_runs=[_to_agent_run_response(r) for r in result.agent_runs],
    )


@router.get(
    "/{conversation_id}/agent-runs",
    response_model=list[AgentRunResponse],
    summary="List every agent invocation for a conversation (observability)",
)
async def list_agent_runs(
    conversation_id: UUID,
    conversation_repo: ConversationRepo,
    agent_run_repo: AgentRunRepo,
    current_user: CurrentUser,
) -> list[AgentRunResponse]:
    conversation = await conversation_repo.get_by_id(conversation_id)
    if conversation is None or conversation.tenant_id != current_user.tenant_id:
        raise EntityNotFoundError("Conversation", conversation_id)
    runs = await agent_run_repo.list_for_conversation(conversation_id)
    return [_to_agent_run_response(r) for r in runs]
