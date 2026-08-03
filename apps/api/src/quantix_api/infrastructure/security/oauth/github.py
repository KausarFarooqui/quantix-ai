"""GitHub OAuth client.

GitHub's OAuth app flow doesn't guarantee a verified public email in the
main user profile, so a second call to ``/user/emails`` picks the primary
verified address when the profile's ``email`` field is null (common when
users keep their email private).
"""

from __future__ import annotations

from quantix_api.application.interfaces.oauth_provider import OAuthUserInfo
from quantix_api.domain.entities.oauth_account import OAuthProviderName
from quantix_api.domain.exceptions.auth import OAuthProviderError
from quantix_api.infrastructure.security.oauth.base import AuthorizationCodeOAuthClient


class GitHubOAuthClient(AuthorizationCodeOAuthClient):
    provider_name = OAuthProviderName.GITHUB
    authorize_base_url = "https://github.com/login/oauth/authorize"
    token_url = "https://github.com/login/oauth/access_token"
    user_url = "https://api.github.com/user"
    emails_url = "https://api.github.com/user/emails"
    scope = "read:user user:email"

    async def exchange_code_for_user_info(self, *, code: str, redirect_uri: str) -> OAuthUserInfo:
        token_payload = await self._exchange_code_for_token(code=code, redirect_uri=redirect_uri)
        access_token = token_payload.get("access_token")
        if not access_token:
            raise OAuthProviderError(self.provider_name.value, "no access_token in response")

        profile = await self._get(self.user_url, access_token=access_token)
        subject = profile.get("id")
        if not subject:
            raise OAuthProviderError(self.provider_name.value, "userinfo missing id")

        email = profile.get("email")
        email_verified = bool(email)
        if not email:
            emails = await self._get(self.emails_url, access_token=access_token)
            primary = next(
                (e for e in emails if isinstance(e, dict) and e.get("primary")), None
            )
            if primary is None:
                raise OAuthProviderError(self.provider_name.value, "no primary email available")
            email = primary["email"]
            email_verified = bool(primary.get("verified", False))

        return OAuthUserInfo(
            provider_user_id=str(subject),
            email=email,
            email_verified=email_verified,
            full_name=profile.get("name") or profile.get("login") or email.split("@")[0],
        )
