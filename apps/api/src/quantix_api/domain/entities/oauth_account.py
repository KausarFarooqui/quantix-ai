"""OAuth account link — connects a Quantix user to an identity at an
external provider (Google/GitHub/Microsoft).

Kept as its own entity rather than columns on ``User`` because a single
user may eventually link multiple providers, and because "is this
provider identity already registered" needs to be looked up independently
of any tenant context during the OAuth callback.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from quantix_api.domain.entities.base import Entity


class OAuthProviderName(StrEnum):
    GOOGLE = "google"
    GITHUB = "github"
    MICROSOFT = "microsoft"


@dataclass(kw_only=True, eq=False)  # see base.Entity docstring — required to inherit identity equality
class OAuthAccount(Entity):
    """One (provider, provider_user_id) → user mapping."""

    user_id: UUID
    provider: OAuthProviderName
    provider_user_id: str
    email_at_provider: str
