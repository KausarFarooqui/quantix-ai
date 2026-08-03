"""Authentication/authorization-specific domain exceptions."""

from __future__ import annotations

from quantix_api.domain.exceptions.base import DomainError


class InvalidCredentialsError(DomainError):
    """Raised on any login failure. Deliberately generic — never reveal
    whether the email exists, only the password was wrong, etc.
    """

    def __init__(self) -> None:
        super().__init__("Invalid email or password")


class InactiveUserError(DomainError):
    def __init__(self) -> None:
        super().__init__("This account is inactive")


class InvalidRefreshTokenError(DomainError):
    def __init__(self) -> None:
        super().__init__("Refresh token is invalid, expired, or has been revoked")


class RefreshTokenReuseError(DomainError):
    """Raised when an already-used (rotated) refresh token is presented
    again — a strong signal of token theft. Callers should revoke the
    entire token family in response.
    """

    def __init__(self) -> None:
        super().__init__("Refresh token reuse detected; all sessions revoked")


class OAuthProviderError(DomainError):
    """Raised when the upstream OAuth provider rejects the exchange or
    returns an unexpected/untrusted response.
    """

    def __init__(self, provider: str, reason: str) -> None:
        self.provider = provider
        self.reason = reason
        super().__init__(f"OAuth exchange with {provider} failed: {reason}")


class InvalidOAuthStateError(DomainError):
    def __init__(self) -> None:
        super().__init__("OAuth state parameter is invalid or expired")
