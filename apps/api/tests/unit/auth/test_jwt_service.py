"""Unit tests for the JWT/opaque-token service."""

from __future__ import annotations

from uuid import uuid4

import pytest

from quantix_api.domain.exceptions.auth import InvalidCredentialsError, InvalidOAuthStateError
from quantix_api.infrastructure.security.jwt_service import JWTTokenService


@pytest.fixture
def token_service() -> JWTTokenService:
    return JWTTokenService(
        secret_key="unit-test-secret-key", algorithm="HS256", access_token_expire_minutes=30
    )


class TestAccessTokens:
    def test_roundtrip_preserves_claims(self, token_service: JWTTokenService) -> None:
        user_id, tenant_id = uuid4(), uuid4()
        token = token_service.create_access_token(user_id=user_id, tenant_id=tenant_id, role="admin")

        claims = token_service.decode_access_token(token)

        assert claims.user_id == user_id
        assert claims.tenant_id == tenant_id
        assert claims.role == "admin"
        assert claims.jti

    def test_decoding_garbage_raises_invalid_credentials(self, token_service: JWTTokenService) -> None:
        with pytest.raises(InvalidCredentialsError):
            token_service.decode_access_token("not-a-real-token")

    def test_decoding_a_token_signed_with_a_different_secret_fails(self) -> None:
        service_a = JWTTokenService(
            secret_key="secret-a", algorithm="HS256", access_token_expire_minutes=30
        )
        service_b = JWTTokenService(
            secret_key="secret-b", algorithm="HS256", access_token_expire_minutes=30
        )
        token = service_a.create_access_token(user_id=uuid4(), tenant_id=uuid4(), role="viewer")

        with pytest.raises(InvalidCredentialsError):
            service_b.decode_access_token(token)

    def test_two_tokens_for_the_same_user_have_different_jti(
        self, token_service: JWTTokenService
    ) -> None:
        user_id, tenant_id = uuid4(), uuid4()
        first = token_service.create_access_token(user_id=user_id, tenant_id=tenant_id, role="viewer")
        second = token_service.create_access_token(user_id=user_id, tenant_id=tenant_id, role="viewer")

        assert token_service.decode_access_token(first).jti != token_service.decode_access_token(
            second
        ).jti


class TestRefreshTokens:
    def test_generated_tokens_are_unique(self, token_service: JWTTokenService) -> None:
        assert token_service.generate_refresh_token() != token_service.generate_refresh_token()

    def test_hash_is_deterministic(self, token_service: JWTTokenService) -> None:
        raw = token_service.generate_refresh_token()
        assert token_service.hash_refresh_token(raw) == token_service.hash_refresh_token(raw)

    def test_different_tokens_hash_differently(self, token_service: JWTTokenService) -> None:
        a, b = token_service.generate_refresh_token(), token_service.generate_refresh_token()
        assert token_service.hash_refresh_token(a) != token_service.hash_refresh_token(b)


class TestOAuthStateTokens:
    def test_roundtrip_preserves_claims(self, token_service: JWTTokenService) -> None:
        token = token_service.create_oauth_state_token(
            nonce="abc123",
            provider="google",
            redirect_uri="https://api.example.com/callback",
            organization_name="Acme Corp",
        )

        claims = token_service.decode_oauth_state_token(token)

        assert claims.nonce == "abc123"
        assert claims.provider == "google"
        assert claims.redirect_uri == "https://api.example.com/callback"
        assert claims.organization_name == "Acme Corp"

    def test_tampered_state_token_is_rejected(self, token_service: JWTTokenService) -> None:
        token = token_service.create_oauth_state_token(
            nonce="abc123", provider="google", redirect_uri="https://x", organization_name=None
        )
        # Flip a character in the middle of the signature segment rather
        # than the last character of the token: base64url's final character
        # can land on padding/don't-care bits, so tampering it is sometimes
        # a no-op and the "tampered" token decodes identically to the
        # original, making this assertion flaky.
        header_b64, payload_b64, signature_b64 = token.split(".")
        mid = len(signature_b64) // 2
        flipped_char = "A" if signature_b64[mid] != "A" else "B"
        tampered_signature = signature_b64[:mid] + flipped_char + signature_b64[mid + 1 :]
        tampered = f"{header_b64}.{payload_b64}.{tampered_signature}"

        with pytest.raises(InvalidOAuthStateError):
            token_service.decode_oauth_state_token(tampered)

    def test_access_token_cannot_be_used_as_oauth_state(self, token_service: JWTTokenService) -> None:
        access_token = token_service.create_access_token(user_id=uuid4(), tenant_id=uuid4(), role="viewer")

        with pytest.raises(InvalidOAuthStateError):
            token_service.decode_oauth_state_token(access_token)
