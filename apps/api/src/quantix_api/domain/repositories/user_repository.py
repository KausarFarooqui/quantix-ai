"""Abstract repository port for ``User`` aggregates."""

from __future__ import annotations

from abc import abstractmethod
from uuid import UUID

from quantix_api.domain.entities.user import User
from quantix_api.domain.repositories.base import AbstractRepository


class UserRepository(AbstractRepository[User]):
    @abstractmethod
    async def get_by_email(self, tenant_id: UUID, email: str) -> User | None:
        """Look up a user by email within a single tenant (email is unique
        per tenant, not globally — see ``UserModel.__table_args__``).
        """
        raise NotImplementedError  # pragma: no cover — abstract; the concrete repository overrides this

    @abstractmethod
    async def email_exists_in_any_tenant(self, email: str) -> bool:
        """Used only for UX hints ("this email is already registered
        elsewhere") — never for authentication decisions.
        """
        raise NotImplementedError  # pragma: no cover — abstract; the concrete repository overrides this
