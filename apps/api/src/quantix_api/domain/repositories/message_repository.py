"""Abstract repository port for ``Message`` aggregates."""

from __future__ import annotations

from abc import abstractmethod
from uuid import UUID

from quantix_api.domain.entities.message import Message
from quantix_api.domain.repositories.base import AbstractRepository


class MessageRepository(AbstractRepository[Message]):
    @abstractmethod
    async def list_for_conversation(self, conversation_id: UUID, *, limit: int = 200) -> list[Message]:
        """Returns messages oldest-first — the order a conversation reads in."""
        raise NotImplementedError  # pragma: no cover — abstract; the concrete repository overrides this
