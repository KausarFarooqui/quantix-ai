"""Concrete SQLAlchemy implementation of
``domain.repositories.message_repository.MessageRepository``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from quantix_api.domain.entities.message import Message
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.domain.repositories.message_repository import MessageRepository
from quantix_api.infrastructure.database.models.message import MessageModel
from quantix_api.infrastructure.database.repositories.sqlalchemy_repository import (
    SQLAlchemyRepository,
)


class SqlAlchemyMessageRepository(SQLAlchemyRepository[Message, MessageModel], MessageRepository):
    model = MessageModel

    def _to_entity(self, record: MessageModel) -> Message:
        return Message(
            id=record.id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            tenant_id=record.tenant_id,
            conversation_id=record.conversation_id,
            role=record.role,
            content=record.content,
            agent_type=record.agent_type,
        )

    def _to_model(self, entity: Message) -> MessageModel:
        return MessageModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            conversation_id=entity.conversation_id,
            role=entity.role,
            content=entity.content,
            agent_type=entity.agent_type,
        )

    async def list_for_conversation(self, conversation_id: UUID, *, limit: int = 200) -> list[Message]:
        stmt = (
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at.asc())
            .limit(limit)
        )
        result = await self._session.scalars(stmt)
        return [self._to_entity(record) for record in result.all()]

    async def update(self, entity: Message) -> Message:
        record = await self._session.get(MessageModel, entity.id)
        if record is None:
            raise EntityNotFoundError("Message", entity.id)
        record.content = entity.content
        record.agent_type = entity.agent_type
        await self._session.flush()
        await self._session.refresh(record)
        return self._to_entity(record)
