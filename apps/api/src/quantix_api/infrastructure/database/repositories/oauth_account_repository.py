"""Concrete SQLAlchemy implementation of
``domain.repositories.oauth_account_repository.OAuthAccountRepository``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from quantix_api.domain.entities.oauth_account import OAuthAccount, OAuthProviderName
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.domain.repositories.oauth_account_repository import OAuthAccountRepository
from quantix_api.infrastructure.database.models.oauth_account import OAuthAccountModel
from quantix_api.infrastructure.database.repositories.sqlalchemy_repository import (
    SQLAlchemyRepository,
)


class SqlAlchemyOAuthAccountRepository(
    SQLAlchemyRepository[OAuthAccount, OAuthAccountModel], OAuthAccountRepository
):
    model = OAuthAccountModel

    def _to_entity(self, record: OAuthAccountModel) -> OAuthAccount:
        return OAuthAccount(
            id=record.id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            user_id=record.user_id,
            provider=record.provider,
            provider_user_id=record.provider_user_id,
            email_at_provider=record.email_at_provider,
        )

    def _to_model(self, entity: OAuthAccount) -> OAuthAccountModel:
        return OAuthAccountModel(
            id=entity.id,
            user_id=entity.user_id,
            provider=entity.provider,
            provider_user_id=entity.provider_user_id,
            email_at_provider=entity.email_at_provider,
        )

    async def get_by_provider_identity(
        self, provider: OAuthProviderName, provider_user_id: str
    ) -> OAuthAccount | None:
        stmt = select(OAuthAccountModel).where(
            OAuthAccountModel.provider == provider,
            OAuthAccountModel.provider_user_id == provider_user_id,
        )
        record = (await self._session.scalars(stmt)).first()
        return self._to_entity(record) if record is not None else None

    async def list_for_user(self, user_id: UUID) -> list[OAuthAccount]:
        stmt = select(OAuthAccountModel).where(OAuthAccountModel.user_id == user_id)
        result = await self._session.scalars(stmt)
        return [self._to_entity(record) for record in result.all()]

    async def update(self, entity: OAuthAccount) -> OAuthAccount:
        record = await self._session.get(OAuthAccountModel, entity.id)
        if record is None:
            raise EntityNotFoundError("OAuthAccount", entity.id)
        record.email_at_provider = entity.email_at_provider
        await self._session.flush()
        await self._session.refresh(record)
        return self._to_entity(record)
