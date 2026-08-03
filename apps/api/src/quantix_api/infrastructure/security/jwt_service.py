"""JWT + opaque-refresh-token implementation of
``application.interfaces.token_service.TokenService``.

Access tokens are signed JWTs (stateless, verified by signature alone).
Refresh tokens are cryptographically random opaque strings — never JWTs —
because they must be revocable server-side; a self-contained JWT refresh
token would defeat that. OAuth state tokens reuse the JWT machinery since
they're short-lived and only need integrity, not confidentiality of a
server-side record.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

from jose import JWTError, jwt

from quantix_api.application.interfaces.token_service import AccessTokenClaims, OAuthStateClaims
from quantix_api.domain.exceptions.auth import InvalidCredentialsError, InvalidOAuthStateError

REFRESH_TOKEN_BYTES = 32
OAUTH_STATE_TTL_MINUTES = 10


class JWTTokenService:
    def __init__(self, *, secret_key: str, algorithm: str, access_token_expire_minutes: int) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._access_token_expire_minutes = access_token_expire_minutes

    @property
    def access_token_ttl_seconds(self) -> int:
        return self._access_token_expire_minutes * 60

    def create_access_token(self, *, user_id: UUID, tenant_id: UUID, role: str) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "role": role,
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": now + timedelta(minutes=self._access_token_expire_minutes),
            "type": "access",
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def decode_access_token(self, token: str) -> AccessTokenClaims:
        try:
            payload = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
        except JWTError as exc:
            raise InvalidCredentialsError from exc

        if payload.get("type") != "access":
            raise InvalidCredentialsError

        try:
            return AccessTokenClaims(
                user_id=UUID(payload["sub"]),
                tenant_id=UUID(payload["tenant_id"]),
                role=payload["role"],
                jti=payload["jti"],
            )
        except (KeyError, ValueError) as exc:
            raise InvalidCredentialsError from exc

    def generate_refresh_token(self) -> str:
        return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)

    def hash_refresh_token(self, raw_token: str) -> str:
        # SHA-256 is appropriate here (unlike passwords): the input is
        # already a high-entropy random token, not a low-entropy secret
        # an attacker could brute-force offline.
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def create_oauth_state_token(
        self, *, nonce: str, provider: str, redirect_uri: str, organization_name: str | None
    ) -> str:
        now = datetime.now(UTC)
        payload = {
            "nonce": nonce,
            "provider": provider,
            "redirect_uri": redirect_uri,
            "organization_name": organization_name,
            "iat": now,
            "exp": now + timedelta(minutes=OAUTH_STATE_TTL_MINUTES),
            "type": "oauth_state",
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def decode_oauth_state_token(self, token: str) -> OAuthStateClaims:
        try:
            payload = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
        except JWTError as exc:
            raise InvalidOAuthStateError from exc

        if payload.get("type") != "oauth_state":
            raise InvalidOAuthStateError

        try:
            return OAuthStateClaims(
                nonce=payload["nonce"],
                provider=payload["provider"],
                redirect_uri=payload["redirect_uri"],
                organization_name=payload.get("organization_name"),
            )
        except KeyError as exc:
            raise InvalidOAuthStateError from exc
