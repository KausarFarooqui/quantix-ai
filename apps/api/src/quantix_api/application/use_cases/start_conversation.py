"""Start a new Conversation, optionally scoped to a Dataset so agents
know what data they're working against from the first turn.
"""

from __future__ import annotations

from uuid import UUID

from quantix_api.application.interfaces.audit_logger import AuditLogger
from quantix_api.domain.entities.audit_log import AuditAction
from quantix_api.domain.entities.conversation import Conversation
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.domain.repositories.conversation_repository import ConversationRepository
from quantix_api.domain.repositories.dataset_repository import DatasetRepository


class StartConversationUseCase:
    def __init__(
        self,
        *,
        conversation_repo: ConversationRepository,
        dataset_repo: DatasetRepository,
        audit_logger: AuditLogger,
    ) -> None:
        self._conversation_repo = conversation_repo
        self._dataset_repo = dataset_repo
        self._audit_logger = audit_logger

    async def execute(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        title: str,
        dataset_id: UUID | None = None,
    ) -> Conversation:
        if dataset_id is not None:
            dataset = await self._dataset_repo.get_by_id(dataset_id)
            if dataset is None or dataset.tenant_id != tenant_id:
                raise EntityNotFoundError("Dataset", dataset_id)

        conversation = Conversation(
            tenant_id=tenant_id,
            title=title,
            dataset_id=dataset_id,
            created_by_user_id=actor_user_id,
        )
        conversation = await self._conversation_repo.add(conversation)

        await self._audit_logger.record(
            action=AuditAction.CONVERSATION_STARTED,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            resource_type="conversation",
            resource_id=str(conversation.id),
            metadata={"dataset_id": str(dataset_id) if dataset_id else None},
        )
        return conversation
