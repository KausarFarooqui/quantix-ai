"""Logout: revoke the presented refresh token.

Idempotent by design — logging out with an already-invalid/missing token
is not an error; the caller's goal ("I should no longer be logged in") is
already satisfied.
"""

from __future__ import annotations

from uuid import UUID

from quantix_api.application.interfaces.audit_logger import AuditLogger
from quantix_api.application.interfaces.token_service import TokenService
from quantix_api.domain.entities.audit_log import AuditAction
from quantix_api.domain.repositories.refresh_token_repository import RefreshTokenRepository


class LogoutUserUseCase:
    def __init__(
        self,
        *,
        refresh_token_repo: RefreshTokenRepository,
        token_service: TokenService,
        audit_logger: AuditLogger,
    ) -> None:
        self._refresh_token_repo = refresh_token_repo
        self._token_service = token_service
        self._audit_logger = audit_logger

    async def execute(
        self,
        raw_refresh_token: str,
        *,
        actor_user_id: UUID,
        tenant_id: UUID,
        ip_address: str | None = None,
    ) -> None:
        token_hash = self._token_service.hash_refresh_token(raw_refresh_token)
        record = await self._refresh_token_repo.get_by_token_hash(token_hash)
        if record is not None and not record.is_revoked:
            record.revoke()
            await self._refresh_token_repo.update(record)

        await self._audit_logger.record(
            action=AuditAction.USER_LOGGED_OUT,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            ip_address=ip_address,
        )
