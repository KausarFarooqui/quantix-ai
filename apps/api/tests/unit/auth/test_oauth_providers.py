"""Unit tests for provider-specific OAuth clients.

Network calls are stubbed by monkeypatching the shared
``_exchange_code_for_token`` / ``_get`` helpers rather than pulling in an
HTTP-mocking dependency — these are plain async methods, so a direct
monkeypatch keeps the test fast and dependency-free.
"""

from __future__ import annotations

import pytest

from quantix_api.domain.exceptions.auth import OAuthProviderError
from quantix_api.infrastructure.security.oauth.github import GitHubOAuthClient
from quantix_api.infrastructure.security.oauth.google import GoogleOAuthClient
from quantix_api.infrastructure.security.oauth.microsoft import MicrosoftOAuthClient


class TestGoogleOAuthClient:
    async def test_exchange_returns_user_info(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = GoogleOAuthClient(client_id="id", client_secret="secret")
        monkeypatch.setattr(
            client, "_exchange_code_for_token", _fake_async_return({"access_token": "tok"})
        )
        monkeypatch.setattr(
            client,
            "_get",
            _fake_async_return(
                {"sub": "google-1", "email": "a@b.com", "email_verified": True, "name": "A B"}
            ),
        )

        info = await client.exchange_code_for_user_info(code="code", redirect_uri="https://x")

        assert info.provider_user_id == "google-1"
        assert info.email == "a@b.com"
        assert info.email_verified is True

    async def test_missing_access_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = GoogleOAuthClient(client_id="id", client_secret="secret")
        monkeypatch.setattr(client, "_exchange_code_for_token", _fake_async_return({}))

        with pytest.raises(OAuthProviderError):
            await client.exchange_code_for_user_info(code="code", redirect_uri="https://x")

    def test_authorization_url_includes_client_id_and_state(self) -> None:
        client = GoogleOAuthClient(client_id="my-client-id", client_secret="secret")

        url = client.build_authorization_url(state="the-state", redirect_uri="https://x/callback")

        assert "client_id=my-client-id" in url
        assert "state=the-state" in url


class TestGitHubOAuthClient:
    async def test_falls_back_to_emails_endpoint_when_profile_email_is_private(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = GitHubOAuthClient(client_id="id", client_secret="secret")
        monkeypatch.setattr(
            client, "_exchange_code_for_token", _fake_async_return({"access_token": "tok"})
        )

        async def fake_get(url: str, *, access_token: str) -> dict:
            if url == client.user_url:
                return {"id": 42, "email": None, "name": "Grace Hopper", "login": "ghopper"}
            return [
                {"email": "not-primary@x.com", "primary": False, "verified": True},
                {"email": "primary@x.com", "primary": True, "verified": True},
            ]

        monkeypatch.setattr(client, "_get", fake_get)

        info = await client.exchange_code_for_user_info(code="code", redirect_uri="https://x")

        assert info.email == "primary@x.com"
        assert info.provider_user_id == "42"


class TestMicrosoftOAuthClient:
    async def test_exchange_returns_user_info(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MicrosoftOAuthClient(client_id="id", client_secret="secret")
        monkeypatch.setattr(
            client, "_exchange_code_for_token", _fake_async_return({"access_token": "tok"})
        )
        monkeypatch.setattr(
            client, "_get", _fake_async_return({"sub": "ms-1", "email": "a@b.com", "name": "A B"})
        )

        info = await client.exchange_code_for_user_info(code="code", redirect_uri="https://x")

        assert info.provider_user_id == "ms-1"
        assert info.email == "a@b.com"


def _fake_async_return(value: object):
    async def _inner(*args: object, **kwargs: object) -> object:
        return value

    return _inner
