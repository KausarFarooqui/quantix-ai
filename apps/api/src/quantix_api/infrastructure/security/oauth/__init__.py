"""OAuth 2.0 provider clients (Google, GitHub, Microsoft)."""

from quantix_api.infrastructure.security.oauth.github import GitHubOAuthClient
from quantix_api.infrastructure.security.oauth.google import GoogleOAuthClient
from quantix_api.infrastructure.security.oauth.microsoft import MicrosoftOAuthClient

__all__ = ["GitHubOAuthClient", "GoogleOAuthClient", "MicrosoftOAuthClient"]
