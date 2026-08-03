"""Google OAuth 2.0 / OpenID Connect client."""

from __future__ import annotations

from quantix_api.application.interfaces.oauth_provider import OAuthUserInfo
from quantix_api.domain.entities.oauth_account import OAuthProviderName
from quantix_api.domain.exceptions.auth import OAuthProviderError
from quantix_api.infrastructure.security.oauth.base import AuthorizationCodeOAuthClient


class GoogleOAuthClient(AuthorizationCodeOAuthClient):
    provider_name = OAuthProviderName.GOOGLE
    authorize_base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"
    scope = "openid email profile"

    async def exchange_code_for_user_info(self, *, code: str, redirect_uri: str) -> OAuthUserInfo:
        token_payload = await self._exchange_code_for_token(code=code, redirect_uri=redirect_uri)
        access_token = token_payload.get("access_token")
        if not access_token:
            raise OAuthProviderError(self.provider_name.value, "no access_token in response")

        profile = await self._get(self.userinfo_url, access_token=access_token)

        subject = profile.get("sub")
        email = profile.get("email")
        if not subject or not email:
            raise OAuthProviderError(self.provider_name.value, "userinfo missing sub/email")

        return OAuthUserInfo(
            provider_user_id=str(subject),
            email=email,
            email_verified=bool(profile.get("email_verified", False)),
            full_name=profile.get("name") or email.split("@")[0],
        )
