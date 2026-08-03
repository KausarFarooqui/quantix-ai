"""Concrete SQLAlchemy implementation of ``domain.repositories.user_repository.UserRepository``."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from quantix_api.domain.entities.user import User
from quantix_api.domain.exceptions.base import EntityNotFoundError
from quantix_api.domain.repositories.user_repository import UserRepository
from quantix_api.infrastructure.database.models.user import UserModel
from quantix_api.infrastructure.database.repositories.sqlalchemy_repository import (
    SQLAlchemyRepository,
)


class SqlAlchemyUserRepository(SQLAlchemyRepository[User, UserModel], UserRepository):
    model = UserModel

    def _to_entity(self, record: UserModel) -> User:
        return User(
            id=record.id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            tenant_id=record.tenant_id,
            email=record.email,
            hashed_password=record.hashed_password,
            full_name=record.full_name,
            role=record.role,
            is_active=record.is_active,
            is_email_verified=record.is_email_verified,
        )

    def _to_model(self, entity: User) -> UserModel:
        return UserModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            email=entity.email,
            hashed_password=entity.hashed_password,
            full_name=entity.full_name,
            role=entity.role,
            is_active=entity.is_active,
            is_email_verified=entity.is_email_verified,
        )

    async def get_by_email(self, tenant_id: UUID, email: str) -> User | None:
        stmt = select(UserModel).where(UserModel.tenant_id == tenant_id, UserModel.email == email)
        record = (await self._session.scalars(stmt)).first()
        return self._to_entity(record) if record is not None else None

    async def email_exists_in_any_tenant(self, email: str) -> bool:
        stmt = select(UserModel.id).where(UserModel.email == email).limit(1)
        result = await self._session.scalars(stmt)
        return result.first() is not None

    async def update(self, entity: User) -> User:
        record = await self._session.get(UserModel, entity.id)
        if record is None:
            raise EntityNotFoundError("User", entity.id)
        record.email = entity.email
        record.hashed_password = entity.hashed_password
        record.full_name = entity.full_name
        record.role = entity.role
        record.is_active = entity.is_active
        record.is_email_verified = entity.is_email_verified
        await self._session.flush()
        await self._session.refresh(record)
        return self._to_entity(record)
