"""OAuth 2.0 authorization-code endpoints (Google/GitHub/Microsoft).

Flow:
1. Client hits ``GET /auth/oauth/{provider}/authorize`` (optionally with
   ``?organization_name=`` when the user is signing up, not logging in)
   and is redirected to the provider.
2. Provider redirects back to ``GET /auth/oauth/{provider}/callback`` —
   this URL (built from ``settings.api_public_url``) is what must be
   registered as the redirect URI in each provider's OAuth app console.
3. We verify ``state`` (a signed, short-TTL JWT — stateless CSRF
   protection, no server-side session needed), exchange the code for the
   provider's identity, find-or-create the Quantix account, and redirect
   the browser to the frontend with tokens in the URL *fragment*
   (``#access_token=...``) rather than the query string — fragments are
   never sent to the server or captured in server access logs, which
   query strings are.

Known simplification (see ADR-0002): handing tokens to the SPA via a
redirect fragment is simpler than a one-time-code exchange but leaves
tokens transiently in browser history/JS-reachable state. Production
hardening should move this to an httpOnly ``Set-Cookie`` + one-time code
exchange; tracked as a follow-up, not a milestone-2 blocker.
"""

from __future__ import annotations

import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse

from quantix_api.core.config import get_settings
from quantix_api.domain.entities.oauth_account import OAuthProviderName
from quantix_api.domain.exceptions.auth import InvalidOAuthStateError
from quantix_api.interface.api.v1.dependencies.auth import ClientIp
from quantix_api.interface.api.v1.dependencies.services import OAuthClientDep, TokenServiceDep
from quantix_api.interface.api.v1.dependencies.use_cases import OAuthLoginUseCaseDep
from quantix_api.interface.api.v1.schemas.auth import OAuthAuthorizeResponse

router = APIRouter(prefix="/auth/oauth", tags=["auth", "oauth"])


def _redirect_uri_for(provider: str) -> str:
    """The redirect_uri registered with the OAuth provider console —
    always points at this backend, since the provider calls it directly.
    """
    settings = get_settings()
    return f"{settings.api_public_url.rstrip('/')}{settings.api_v1_prefix}/auth/oauth/{provider}/callback"


@router.get(
    "/{provider}/authorize",
    response_model=OAuthAuthorizeResponse,
    summary="Get the provider's authorization URL to redirect the browser to",
)
async def authorize(
    provider: str,
    oauth_client: OAuthClientDep,
    token_service: TokenServiceDep,
    organization_name: str | None = Query(
        default=None, description="Only used if this becomes a new-tenant signup"
    ),
) -> OAuthAuthorizeResponse:
    redirect_uri = _redirect_uri_for(provider)

    state = token_service.create_oauth_state_token(
        nonce=secrets.token_urlsafe(16),
        provider=provider,
        redirect_uri=redirect_uri,
        organization_name=organization_name,
    )
    url = oauth_client.build_authorization_url(state=state, redirect_uri=redirect_uri)
    return OAuthAuthorizeResponse(authorization_url=url)


@router.get("/{provider}/callback", summary="OAuth provider redirects here after user consent")
async def callback(
    provider: str,
    code: str,
    state: str,
    oauth_client: OAuthClientDep,
    token_service: TokenServiceDep,
    use_case: OAuthLoginUseCaseDep,
    ip_address: ClientIp,
) -> RedirectResponse:
    settings = get_settings()
    state_claims = token_service.decode_oauth_state_token(state)

    if state_claims.provider != provider:
        raise InvalidOAuthStateError

    user_info = await oauth_client.exchange_code_for_user_info(
        code=code, redirect_uri=state_claims.redirect_uri
    )

    result = await use_case.execute(
        provider=OAuthProviderName(provider),
        user_info=user_info,
        organization_name_hint=state_claims.organization_name,
        ip_address=ip_address,
    )

    fragment = urlencode(
        {
            "access_token": result.tokens.access_token,
            "refresh_token": result.tokens.refresh_token,
            "expires_in": result.tokens.expires_in,
            "is_new_account": str(result.is_new_account).lower(),
        }
    )
    redirect_url = f"{settings.frontend_url.rstrip('/')}/auth/callback#{fragment}"
    return RedirectResponse(url=redirect_url, status_code=302)
