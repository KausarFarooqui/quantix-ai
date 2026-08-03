"""Refresh-token rotation: exchange a valid refresh token for a new
access+refresh pair, revoking the presented token in the same operation.

Reuse detection: if a token that's already been revoked (i.e. already
rotated once, or explicitly logged out) is presented again, that's a
strong signal it was stolen and used concurrently with the legitimate
client — the entire refresh-token family for that user is revoked in
response.
"""

from __future__ import annotations

from quantix_api.application.dto.auth import AuthResult
from quantix_api.application.interfaces.audit_logger import AuditLogger
from quantix_api.application.interfaces.token_service import TokenService
from quantix_api.application.use_cases._token_issuance import issue_tokens
from quantix_api.domain.entities.audit_log import AuditAction
from quantix_api.domain.exceptions.auth import (
    InvalidRefreshTokenError,
    RefreshTokenReuseError,
)
from quantix_api.domain.repositories.refresh_token_repository import RefreshTokenRepository
from quantix_api.domain.repositories.user_repository import UserRepository


class RefreshAccessTokenUseCase:
    def __init__(
        self,
        *,
        refresh_token_repo: RefreshTokenRepository,
        user_repo: UserRepository,
        token_service: TokenService,
        audit_logger: AuditLogger,
    ) -> None:
        self._refresh_token_repo = refresh_token_repo
        self._user_repo = user_repo
        self._token_service = token_service
        self._audit_logger = audit_logger

    async def execute(self, raw_refresh_token: str, *, ip_address: str | None = None) -> AuthResult:
        token_hash = self._token_service.hash_refresh_token(raw_refresh_token)
        record = await self._refresh_token_repo.get_by_token_hash(token_hash)

        if record is None:
            raise InvalidRefreshTokenError

        if record.is_revoked:
            await self._refresh_token_repo.revoke_all_for_user(record.user_id)
            await self._audit_logger.record(
                action=AuditAction.TOKEN_REUSE_DETECTED,
                tenant_id=record.tenant_id,
                actor_user_id=record.user_id,
                ip_address=ip_address,
            )
            raise RefreshTokenReuseError

        if record.is_expired:
            raise InvalidRefreshTokenError

        user = await self._user_repo.get_by_id(record.user_id)
        if user is None or not user.is_active:
            raise InvalidRefreshTokenError

        tokens = await issue_tokens(
            user=user,
            token_service=self._token_service,
            refresh_token_repo=self._refresh_token_repo,
            replaces=record.id,
        )

        await self._audit_logger.record(
            action=AuditAction.TOKEN_REFRESHED,
            tenant_id=user.tenant_id,
            actor_user_id=user.id,
            ip_address=ip_address,
        )

        return AuthResult(tokens=tokens, user_id=user.id, tenant_id=user.tenant_id)
