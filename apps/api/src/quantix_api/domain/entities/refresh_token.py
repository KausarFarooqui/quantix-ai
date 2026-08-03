"""Refresh token domain entity.

Refresh tokens are the one piece of "session" state we keep server-side:
access tokens are stateless JWTs that can't be revoked before they expire,
so anything that needs real revocation (logout, rotation, "log out
everywhere") hangs off this record instead. Only a SHA-256 hash of the
token is ever persisted — the raw token is shown to the client exactly
once, at issuance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from quantix_api.domain.entities.base import Entity


@dataclass(kw_only=True, eq=False)  # see base.Entity docstring — required to inherit identity equality
class RefreshToken(Entity):
    """A single refresh-token grant, revocable independently of others."""

    user_id: UUID
    tenant_id: UUID
    token_hash: str
    expires_at: datetime
    revoked_at: datetime | None = None
    replaced_by_id: UUID | None = None  # set on rotation, forms an audit chain

    @property
    def is_expired(self) -> bool:
        # SQLite (used in the test suite; see conftest.py) doesn't have a
        # real "timestamp with timezone" type, so a `DateTime(timezone=True)`
        # column round-trips through it as naive — Postgres preserves
        # tzinfo natively. Every timestamp in this system is UTC by
        # convention, so a naive value here is assumed to already be UTC
        # rather than treated as an error.
        expires_at = self.expires_at if self.expires_at.tzinfo is not None else self.expires_at.replace(tzinfo=UTC)
        return datetime.now(UTC) >= expires_at

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_active(self) -> bool:
        return not self.is_expired and not self.is_revoked

    def revoke(self) -> None:
        if self.revoked_at is None:
            self.revoked_at = datetime.now(UTC)
