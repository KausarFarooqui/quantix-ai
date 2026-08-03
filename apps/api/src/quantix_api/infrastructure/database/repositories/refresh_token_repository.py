"""Concrete SQLAlchemy implementation of
``domain.repositories.refresh_token_repository.RefreshTokenRepository``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, update

from quantix_api.domain.entities.refresh_token import RefreshToken
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.domain.repositories.refresh_token_repository import RefreshTokenRepository
from quantix_api.infrastructure.database.models.refresh_token import RefreshTokenModel
from quantix_api.infrastructure.database.repositories.sqlalchemy_repository import (
    SQLAlchemyRepository,
)

class SqlAlchemyRefreshTokenRepository(
    SQLAlchemyRepository[RefreshToken, RefreshTokenModel], RefreshTokenRepository
):
    model = RefreshTokenModel

    def _to_entity(self, record: RefreshTokenModel) -> RefreshToken:
        return RefreshToken(
            id=record.id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            tenant_id=record.tenant_id,
            user_id=record.user_id,
            token_hash=record.token_hash,
            expires_at=record.expires_at,
            revoked_at=record.revoked_at,
            replaced_by_id=record.replaced_by_id,
        )

    def _to_model(self, entity: RefreshToken) -> RefreshTokenModel:
        return RefreshTokenModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            user_id=entity.user_id,
            token_hash=entity.token_hash,
            expires_at=entity.expires_at,
            revoked_at=entity.revoked_at,
            replaced_by_id=entity.replaced_by_id,
        )

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        record = (await self._session.scalars(stmt)).first()
        return self._to_entity(record) if record is not None else None

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        stmt = (
            update(RefreshTokenModel)
            .where(RefreshTokenModel.user_id == user_id, RefreshTokenModel.revoked_at.is_(None))
            .values(revoked_at=func.now())
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def update(self, entity: RefreshToken) -> RefreshToken:
        record = await self._session.get(RefreshTokenModel, entity.id)
        if record is None:
            raise EntityNotFoundError("RefreshToken", entity.id)
        record.revoked_at = entity.revoked_at
        record.replaced_by_id = entity.replaced_by_id
        await self._session.flush()
        await self._session.refresh(record)
        return self._to_entity(record)
