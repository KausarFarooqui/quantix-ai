"""Abstract repository port for ``OAuthAccount`` aggregates."""

from __future__ import annotations

from abc import abstractmethod
from uuid import UUID

from quantix_api.domain.entities.oauth_account import OAuthAccount, OAuthProviderName
from quantix_api.domain.repositories.base import AbstractRepository


class OAuthAccountRepository(AbstractRepository[OAuthAccount]):
    @abstractmethod
    async def get_by_provider_identity(
        self, provider: OAuthProviderName, provider_user_id: str
    ) -> OAuthAccount | None:
        raise NotImplementedError  # pragma: no cover — abstract; the concrete repository overrides this

    @abstractmethod
    async def list_for_user(self, user_id: UUID) -> list[OAuthAccount]:
        raise NotImplementedError  # pragma: no cover — abstract; the concrete repository overrides this
