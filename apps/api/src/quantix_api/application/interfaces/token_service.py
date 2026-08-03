"""Port for access-token / refresh-token / OAuth-state cryptographic
operations — implemented by ``infrastructure.security.jwt_service``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    user_id: UUID
    tenant_id: UUID
    role: str
    jti: str


@dataclass(frozen=True, slots=True)
class OAuthStateClaims:
    nonce: str
    provider: str
    redirect_uri: str
    organization_name: str | None


class TokenService(Protocol):
    def create_access_token(self, *, user_id: UUID, tenant_id: UUID, role: str) -> str: ...

    def decode_access_token(self, token: str) -> AccessTokenClaims:
        """Raise ``InvalidCredentialsError``-compatible errors via the
        caller; implementations raise ``jose.JWTError`` subclasses which
        the interface layer translates.
        """
        ...

    @property
    def access_token_ttl_seconds(self) -> int: ...

    def generate_refresh_token(self) -> str:
        """Return a new opaque, cryptographically random refresh token."""
        ...

    def hash_refresh_token(self, raw_token: str) -> str:
        """Deterministic hash used for storage/lookup — never store the
        raw token.
        """
        ...

    def create_oauth_state_token(
        self, *, nonce: str, provider: str, redirect_uri: str, organization_name: str | None
    ) -> str: ...

    def decode_oauth_state_token(self, token: str) -> OAuthStateClaims: ...
