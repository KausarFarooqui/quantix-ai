"""Abstract repository port for ``RefreshToken`` aggregates."""

from __future__ import annotations

from abc import abstractmethod
from uuid import UUID

from quantix_api.domain.entities.refresh_token import RefreshToken
from quantix_api.domain.repositories.base import AbstractRepository


class RefreshTokenRepository(AbstractRepository[RefreshToken]):
    @abstractmethod
    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        raise NotImplementedError  # pragma: no cover — abstract; the concrete repository overrides this

    @abstractmethod
    async def revoke_all_for_user(self, user_id: UUID) -> None:
        """Revoke every active refresh token for a user — used on password
        change, suspicious activity, or explicit "log out everywhere".
        """
        raise NotImplementedError  # pragma: no cover — abstract; the concrete repository overrides this
