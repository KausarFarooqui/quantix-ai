"""Unit tests for the Fernet-based credential cipher."""

from __future__ import annotations

import pytest

from quantix_api.infrastructure.security.credential_cipher import FernetCredentialCipher


class TestFernetCredentialCipher:
    def test_roundtrip(self) -> None:
        cipher = FernetCredentialCipher(encryption_key="test-key")
        secrets = {"username": "admin", "password": "hunter2"}

        ciphertext = cipher.encrypt(secrets)
        decrypted = cipher.decrypt(ciphertext)

        assert decrypted == secrets

    def test_ciphertext_does_not_contain_plaintext_secrets(self) -> None:
        cipher = FernetCredentialCipher(encryption_key="test-key")
        ciphertext = cipher.encrypt({"password": "super-secret-value"})

        assert "super-secret-value" not in ciphertext

    def test_different_keys_cannot_decrypt_each_others_ciphertext(self) -> None:
        cipher_a = FernetCredentialCipher(encryption_key="key-a")
        cipher_b = FernetCredentialCipher(encryption_key="key-b")
        ciphertext = cipher_a.encrypt({"password": "secret"})

        with pytest.raises(ValueError, match="invalid"):
            cipher_b.decrypt(ciphertext)

    def test_tampered_ciphertext_is_rejected(self) -> None:
        cipher = FernetCredentialCipher(encryption_key="test-key")
        ciphertext = cipher.encrypt({"password": "secret"})
        tampered = ciphertext[:-4] + ("AAAA" if not ciphertext.endswith("AAAA") else "BBBB")

        with pytest.raises(ValueError, match="invalid"):
            cipher.decrypt(tampered)
