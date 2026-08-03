"""ORM model for conversation messages."""

from __future__ import annotations

import uuid

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from quantix_api.domain.entities.agent_run import AgentType
from quantix_api.domain.entities.message import MessageRole
from quantix_api.infrastructure.database.models.base import (
    Base,
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class MessageModel(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, name="message_role", native_enum=True), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    agent_type: Mapped[AgentType | None] = mapped_column(
        Enum(AgentType, name="agent_type", native_enum=True), nullable=True
    )
