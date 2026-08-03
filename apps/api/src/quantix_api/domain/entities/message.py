"""Message domain entity — one turn in a Conversation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from quantix_api.domain.entities.agent_run import AgentType
from quantix_api.domain.entities.base import TenantScopedEntity


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass(kw_only=True, eq=False)  # see base.Entity docstring — required to inherit identity equality
class Message(TenantScopedEntity):
    conversation_id: UUID
    role: MessageRole
    content: str
    # Set on assistant messages produced by a specialized agent (as opposed
    # to the supervisor's own clarifying text, or a plain user message).
    agent_type: AgentType | None = None
