"""Concrete SQLAlchemy implementation of
``domain.repositories.agent_run_repository.AgentRunRepository``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from quantix_api.domain.entities.agent_run import AgentRun
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.domain.repositories.agent_run_repository import AgentRunRepository
from quantix_api.infrastructure.database.models.agent_run import AgentRunModel
from quantix_api.infrastructure.database.repositories.sqlalchemy_repository import (
    SQLAlchemyRepository,
)


class SqlAlchemyAgentRunRepository(SQLAlchemyRepository[AgentRun, AgentRunModel], AgentRunRepository):
    model = AgentRunModel

    def _to_entity(self, record: AgentRunModel) -> AgentRun:
        return AgentRun(
            id=record.id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            tenant_id=record.tenant_id,
            conversation_id=record.conversation_id,
            message_id=record.message_id,
            agent_type=record.agent_type,
            status=record.status,
            input_summary=record.input_summary,
            output_summary=record.output_summary,
            tool_calls=record.tool_calls or [],
            prompt_tokens=record.prompt_tokens,
            completion_tokens=record.completion_tokens,
            latency_ms=record.latency_ms,
            error_message=record.error_message,
        )

    def _to_model(self, entity: AgentRun) -> AgentRunModel:
        return AgentRunModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            conversation_id=entity.conversation_id,
            message_id=entity.message_id,
            agent_type=entity.agent_type,
            status=entity.status,
            input_summary=entity.input_summary,
            output_summary=entity.output_summary,
            tool_calls=entity.tool_calls,
            prompt_tokens=entity.prompt_tokens,
            completion_tokens=entity.completion_tokens,
            latency_ms=entity.latency_ms,
            error_message=entity.error_message,
        )

    async def list_for_conversation(self, conversation_id: UUID) -> list[AgentRun]:
        stmt = (
            select(AgentRunModel)
            .where(AgentRunModel.conversation_id == conversation_id)
            .order_by(AgentRunModel.created_at.asc())
        )
        result = await self._session.scalars(stmt)
        return [self._to_entity(record) for record in result.all()]

    async def update(self, entity: AgentRun) -> AgentRun:
        record = await self._session.get(AgentRunModel, entity.id)
        if record is None:
            raise EntityNotFoundError("AgentRun", entity.id)
        record.message_id = entity.message_id
        record.status = entity.status
        record.output_summary = entity.output_summary
        record.tool_calls = entity.tool_calls
        record.prompt_tokens = entity.prompt_tokens
        record.completion_tokens = entity.completion_tokens
        record.latency_ms = entity.latency_ms
        record.error_message = entity.error_message
        await self._session.flush()
        await self._session.refresh(record)
        return self._to_entity(record)
