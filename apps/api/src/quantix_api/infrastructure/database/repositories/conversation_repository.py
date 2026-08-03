"""Concrete SQLAlchemy implementation of
``domain.repositories.conversation_repository.ConversationRepository``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from quantix_api.domain.entities.conversation import Conversation
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.domain.repositories.conversation_repository import ConversationRepository
from quantix_api.infrastructure.database.models.conversation import ConversationModel
from quantix_api.infrastructure.database.repositories.sqlalchemy_repository import (
    SQLAlchemyRepository,
)


class SqlAlchemyConversationRepository(
    SQLAlchemyRepository[Conversation, ConversationModel], ConversationRepository
):
    model = ConversationModel

    def _to_entity(self, record: ConversationModel) -> Conversation:
        return Conversation(
            id=record.id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            tenant_id=record.tenant_id,
            title=record.title,
            dataset_id=record.dataset_id,
            created_by_user_id=record.created_by_user_id,
            status=record.status,
        )

    def _to_model(self, entity: Conversation) -> ConversationModel:
        return ConversationModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            title=entity.title,
            dataset_id=entity.dataset_id,
            created_by_user_id=entity.created_by_user_id,
            status=entity.status,
        )

    async def list_for_tenant(self, tenant_id: UUID, *, limit: int = 50) -> list[Conversation]:
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.tenant_id == tenant_id)
            .order_by(ConversationModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.scalars(stmt)
        return [self._to_entity(record) for record in result.all()]

    async def update(self, entity: Conversation) -> Conversation:
        record = await self._session.get(ConversationModel, entity.id)
        if record is None:
            raise EntityNotFoundError("Conversation", entity.id)
        record.title = entity.title
        record.status = entity.status
        await self._session.flush()
        await self._session.refresh(record)
        return self._to_entity(record)
