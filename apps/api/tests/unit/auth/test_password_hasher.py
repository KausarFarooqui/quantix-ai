"""Unit tests for the Argon2 password hasher."""

from __future__ import annotations

from quantix_api.infrastructure.security.password_hasher import Argon2PasswordHasher


class TestArgon2PasswordHasher:
    def test_verify_succeeds_for_correct_password(self) -> None:
        hasher = Argon2PasswordHasher()
        hashed = hasher.hash("correct horse battery staple")

        assert hasher.verify("correct horse battery staple", hashed) is True

    def test_verify_fails_for_wrong_password(self) -> None:
        hasher = Argon2PasswordHasher()
        hashed = hasher.hash("correct horse battery staple")

        assert hasher.verify("wrong password", hashed) is False

    def test_hash_is_never_the_plaintext(self) -> None:
        hasher = Argon2PasswordHasher()
        hashed = hasher.hash("correct horse battery staple")

        assert hashed != "correct horse battery staple"
        assert hashed.startswith("$argon2")

    def test_hashing_the_same_password_twice_produces_different_hashes(self) -> None:
        # Argon2 salts each hash independently — this guards against a
        # regression that would make hashes comparable/rainbow-tableable.
        hasher = Argon2PasswordHasher()
        assert hasher.hash("same-password") != hasher.hash("same-password")

    def test_freshly_hashed_password_does_not_need_rehash(self) -> None:
        hasher = Argon2PasswordHasher()
        hashed = hasher.hash("correct horse battery staple")

        assert hasher.needs_rehash(hashed) is False
