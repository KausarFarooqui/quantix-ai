"""Shared HTTP helpers for OAuth 2.0 authorization-code exchange.

Each provider client (Google/GitHub/Microsoft) subclasses
``AuthorizationCodeOAuthClient`` and supplies its endpoints + response
parsing — the request plumbing (POST the code, handle non-2xx, timeouts)
lives here once.
"""

from __future__ import annotations

from urllib.parse import urlencode

import httpx

from quantix_api.domain.entities.oauth_account import OAuthProviderName
from quantix_api.domain.exceptions.auth import OAuthProviderError

_HTTP_TIMEOUT_SECONDS = 10.0


class AuthorizationCodeOAuthClient:
    provider_name: OAuthProviderName
    authorize_base_url: str
    token_url: str
    scope: str

    def __init__(self, *, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret

    def build_authorization_url(self, *, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "scope": self.scope,
            "state": state,
            "response_type": "code",
        }
        return f"{self.authorize_base_url}?{urlencode(params)}"

    async def _exchange_code_for_token(
        self, *, code: str, redirect_uri: str, extra_headers: dict[str, str] | None = None
    ) -> dict:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                headers={"Accept": "application/json", **(extra_headers or {})},
            )
        if response.status_code >= 400:
            raise OAuthProviderError(
                self.provider_name.value, f"token exchange returned {response.status_code}"
            )
        return response.json()

    async def _get(self, url: str, *, access_token: str) -> dict:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
        if response.status_code >= 400:
            raise OAuthProviderError(
                self.provider_name.value, f"userinfo request returned {response.status_code}"
            )
        return response.json()
