"""In-memory fakes for agent-orchestration unit tests.

Named ``_agent_fakes.py``, not the generic ``_fakes.py`` — see the
docstring in ``tests/unit/auth/_auth_fakes.py`` for why every fakes
module in this test tree has a directory-unique name (pytest's rootless
import mode collides same-named modules across directories).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pyarrow as pa

from quantix_api.application.interfaces.agent_graph import AgentState
from quantix_api.application.interfaces.llm_client import LLMResponse
from quantix_api.domain.entities.agent_run import AgentRun
from quantix_api.domain.entities.conversation import Conversation
from quantix_api.domain.entities.dataset import Dataset
from quantix_api.domain.entities.forecast import Forecast
from quantix_api.domain.entities.message import Message
from quantix_api.domain.exceptions.base import EntityNotFoundError


class FakeLLMClient:
    """Returns pre-scripted responses in order. An item may be an
    ``LLMResponse`` (returned) or an ``Exception`` instance (raised) —
    lets a single test script both success and failure legs of a loop.
    """

    def __init__(self, responses: list[LLMResponse | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self, *, messages, system, tools=None, tool_choice="auto", max_tokens=4096
    ) -> LLMResponse:
        self.calls.append(
            {"messages": messages, "system": system, "tools": tools, "tool_choice": tool_choice}
        )
        if not self._responses:
            raise AssertionError("FakeLLMClient exhausted its scripted responses")
        next_item = self._responses.pop(0)
        if isinstance(next_item, Exception):
            raise next_item
        return next_item


class FakeDatasetStorage:
    def __init__(self) -> None:
        self._tables: dict[str, pa.Table] = {}

    def put(self, storage_uri: str, table: pa.Table) -> None:
        self._tables[storage_uri] = table

    def write(self, *, tenant_id: UUID, dataset_id: UUID, table: pa.Table) -> tuple[str, int]:
        uri = f"memory://{tenant_id}/{dataset_id}"
        self._tables[uri] = table
        return uri, table.nbytes

    def read_preview(self, *, storage_uri: str, limit: int = 100) -> pa.Table:
        return self._tables[storage_uri].slice(0, limit)

    def query(self, *, storage_uri: str, sql: str, limit: int = 1000) -> pa.Table:
        return self._tables[storage_uri].slice(0, limit)

    def delete(self, *, storage_uri: str) -> None:
        self._tables.pop(storage_uri, None)


class FakeSyncDatasetUseCase:
    def __init__(self, *, resync_result=None, raises: Exception | None = None) -> None:
        self._resync_result = resync_result
        self._raises = raises
        self.resync_calls: list[dict[str, Any]] = []

    async def resync(self, *, tenant_id, dataset_id, actor_user_id):
        self.resync_calls.append(
            {"tenant_id": tenant_id, "dataset_id": dataset_id, "actor_user_id": actor_user_id}
        )
        if self._raises is not None:
            raise self._raises
        return self._resync_result


class FakeAgentGraph:
    """Scripted ``AgentGraph`` — returns a fixed final state (or raises)
    rather than actually running LangGraph, for use-case-level tests that
    only care about what ``SendMessageUseCase`` does with the result.
    """

    def __init__(self, *, final_state: AgentState) -> None:
        self._final_state = final_state
        self.run_calls: list[dict[str, Any]] = []

    async def run(self, *, state, context):
        self.run_calls.append({"state": state, "context": context})
        return self._final_state


class FakeConversationRepository:
    def __init__(self) -> None:
        self.store: dict[UUID, Conversation] = {}

    async def get_by_id(self, entity_id: UUID) -> Conversation | None:
        return self.store.get(entity_id)

    async def add(self, entity: Conversation) -> Conversation:
        self.store[entity.id] = entity
        return entity

    async def update(self, entity: Conversation) -> Conversation:
        if entity.id not in self.store:
            raise EntityNotFoundError("Conversation", entity.id)
        self.store[entity.id] = entity
        return entity

    async def delete(self, entity_id: UUID) -> None:
        self.store.pop(entity_id, None)

    async def list_for_tenant(self, tenant_id: UUID, *, limit: int = 50) -> list[Conversation]:
        return [c for c in self.store.values() if c.tenant_id == tenant_id][:limit]


class FakeMessageRepository:
    def __init__(self) -> None:
        self.store: dict[UUID, Message] = {}

    async def get_by_id(self, entity_id: UUID) -> Message | None:
        return self.store.get(entity_id)

    async def add(self, entity: Message) -> Message:
        self.store[entity.id] = entity
        return entity

    async def update(self, entity: Message) -> Message:
        if entity.id not in self.store:
            raise EntityNotFoundError("Message", entity.id)
        self.store[entity.id] = entity
        return entity

    async def delete(self, entity_id: UUID) -> None:
        self.store.pop(entity_id, None)

    async def list_for_conversation(self, conversation_id: UUID, *, limit: int = 200) -> list[Message]:
        matches = [m for m in self.store.values() if m.conversation_id == conversation_id]
        return sorted(matches, key=lambda m: m.created_at)[:limit]


class FakeAgentRunRepository:
    def __init__(self) -> None:
        self.store: dict[UUID, AgentRun] = {}

    async def get_by_id(self, entity_id: UUID) -> AgentRun | None:
        return self.store.get(entity_id)

    async def add(self, entity: AgentRun) -> AgentRun:
        self.store[entity.id] = entity
        return entity

    async def update(self, entity: AgentRun) -> AgentRun:
        if entity.id not in self.store:
            raise EntityNotFoundError("AgentRun", entity.id)
        self.store[entity.id] = entity
        return entity

    async def delete(self, entity_id: UUID) -> None:
        self.store.pop(entity_id, None)

    async def list_for_conversation(self, conversation_id: UUID) -> list[AgentRun]:
        return [r for r in self.store.values() if r.conversation_id == conversation_id]


class FakeAuditLogger:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    async def record(self, **kwargs: Any) -> None:
        self.records.append(kwargs)


class FakeDatasetRepository:
    """Minimal enough for ``GenerateForecastUseCase`` to look datasets up
    by id — not a full repository fake, since nothing here exercises
    ``list_for_tenant``/``list_for_data_source``.
    """

    def __init__(self, *, datasets: dict[UUID, Dataset] | None = None) -> None:
        self.store: dict[UUID, Dataset] = dict(datasets or {})

    async def get_by_id(self, entity_id: UUID) -> Dataset | None:
        return self.store.get(entity_id)

    async def add(self, entity: Dataset) -> Dataset:
        self.store[entity.id] = entity
        return entity

    async def update(self, entity: Dataset) -> Dataset:
        if entity.id not in self.store:
            raise EntityNotFoundError("Dataset", entity.id)
        self.store[entity.id] = entity
        return entity

    async def delete(self, entity_id: UUID) -> None:
        self.store.pop(entity_id, None)


class FakeForecastRepository:
    def __init__(self) -> None:
        self.store: dict[UUID, Forecast] = {}

    async def get_by_id(self, entity_id: UUID) -> Forecast | None:
        return self.store.get(entity_id)

    async def add(self, entity: Forecast) -> Forecast:
        self.store[entity.id] = entity
        return entity

    async def update(self, entity: Forecast) -> Forecast:
        if entity.id not in self.store:
            raise EntityNotFoundError("Forecast", entity.id)
        self.store[entity.id] = entity
        return entity

    async def delete(self, entity_id: UUID) -> None:
        self.store.pop(entity_id, None)

    async def list_for_dataset(self, dataset_id: UUID) -> list[Forecast]:
        return [f for f in self.store.values() if f.dataset_id == dataset_id]

    async def list_for_tenant(self, tenant_id: UUID) -> list[Forecast]:
        return [f for f in self.store.values() if f.tenant_id == tenant_id]
