"""Pydantic request/response schemas for conversations, messages, and
agent runs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from quantix_api.domain.entities.agent_run import AgentRunStatus, AgentType
from quantix_api.domain.entities.conversation import ConversationStatus
from quantix_api.domain.entities.message import MessageRole


class ConversationCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    dataset_id: UUID | None = None


class ConversationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    title: str
    dataset_id: UUID | None
    status: ConversationStatus
    created_at: datetime


class MessageCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class MessageResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    agent_type: AgentType | None
    created_at: datetime


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    agent_type: AgentType
    status: AgentRunStatus
    output_summary: str | None
    tool_calls: list[dict[str, Any]]
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int | None
    error_message: str | None
    created_at: datetime


class SendMessageResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    message: MessageResponse
    agent_runs: list[AgentRunResponse]
