"""Abstract repository port for ``Conversation`` aggregates."""

from __future__ import annotations

from abc import abstractmethod
from uuid import UUID

from quantix_api.domain.entities.conversation import Conversation
from quantix_api.domain.repositories.base import AbstractRepository


class ConversationRepository(AbstractRepository[Conversation]):
    @abstractmethod
    async def list_for_tenant(self, tenant_id: UUID, *, limit: int = 50) -> list[Conversation]:
        raise NotImplementedError  # pragma: no cover — abstract; the concrete repository overrides this
