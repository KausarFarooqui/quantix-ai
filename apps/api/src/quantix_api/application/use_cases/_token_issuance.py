"""Shared helper: issue an access+refresh token pair and persist the
refresh token record. Used by every use case that ends in "the caller is
now authenticated" (register, login, refresh, OAuth login).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from quantix_api.application.dto.auth import AuthTokens
from quantix_api.application.interfaces.token_service import TokenService
from quantix_api.domain.entities.refresh_token import RefreshToken
from quantix_api.domain.entities.user import User
from quantix_api.domain.repositories.refresh_token_repository import RefreshTokenRepository

REFRESH_TOKEN_TTL_DAYS_DEFAULT = 14


async def issue_tokens(
    *,
    user: User,
    token_service: TokenService,
    refresh_token_repo: RefreshTokenRepository,
    refresh_token_ttl_days: int = REFRESH_TOKEN_TTL_DAYS_DEFAULT,
    replaces: UUID | None = None,
) -> AuthTokens:
    access_token = token_service.create_access_token(
        user_id=user.id, tenant_id=user.tenant_id, role=user.role.value
    )

    raw_refresh_token = token_service.generate_refresh_token()
    refresh_record = RefreshToken(
        user_id=user.id,
        tenant_id=user.tenant_id,
        token_hash=token_service.hash_refresh_token(raw_refresh_token),
        expires_at=datetime.now(UTC) + timedelta(days=refresh_token_ttl_days),
    )
    await refresh_token_repo.add(refresh_record)

    if replaces is not None:
        old = await refresh_token_repo.get_by_id(replaces)
        if old is not None:
            old.revoke()
            old.replaced_by_id = refresh_record.id
            await refresh_token_repo.update(old)

    return AuthTokens(
        access_token=access_token,
        refresh_token=raw_refresh_token,
        expires_in=token_service.access_token_ttl_seconds,
    )
