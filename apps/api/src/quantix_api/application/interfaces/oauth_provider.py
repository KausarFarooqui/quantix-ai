"""Port for OAuth identity providers — implemented per-provider under
``infrastructure.security.oauth``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from quantix_api.domain.entities.oauth_account import OAuthProviderName


@dataclass(frozen=True, slots=True)
class OAuthUserInfo:
    provider_user_id: str
    email: str
    email_verified: bool
    full_name: str


class OAuthProviderClient(Protocol):
    provider_name: OAuthProviderName

    def build_authorization_url(self, *, state: str, redirect_uri: str) -> str:
        """Return the URL the browser should be redirected to."""
        ...

    async def exchange_code_for_user_info(self, *, code: str, redirect_uri: str) -> OAuthUserInfo:
        """Exchange an authorization code for the provider's identity
        info. Raises ``OAuthProviderError`` on any upstream failure.
        """
        ...
