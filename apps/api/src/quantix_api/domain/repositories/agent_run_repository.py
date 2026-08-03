"""Abstract repository port for ``AgentRun`` aggregates."""

from __future__ import annotations

from abc import abstractmethod
from uuid import UUID

from quantix_api.domain.entities.agent_run import AgentRun
from quantix_api.domain.repositories.base import AbstractRepository


class AgentRunRepository(AbstractRepository[AgentRun]):
    @abstractmethod
    async def list_for_conversation(self, conversation_id: UUID) -> list[AgentRun]:
        raise NotImplementedError  # pragma: no cover — abstract; the concrete repository overrides this
