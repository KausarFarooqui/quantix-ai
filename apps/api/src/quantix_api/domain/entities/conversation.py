"""Conversation domain entity — a chat thread with the agent system,
optionally scoped to one Dataset (so agents know what data they're
working against without the user re-stating it every turn).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from quantix_api.domain.entities.base import TenantScopedEntity


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass(kw_only=True, eq=False)  # see base.Entity docstring — required to inherit identity equality
class Conversation(TenantScopedEntity):
    title: str
    dataset_id: UUID | None = None
    created_by_user_id: UUID
    status: ConversationStatus = ConversationStatus.ACTIVE

    def archive(self) -> None:
        self.status = ConversationStatus.ARCHIVED

    def rename(self, title: str) -> None:
        self.title = title
