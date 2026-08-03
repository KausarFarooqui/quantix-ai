"""Port for encrypting connector secrets (passwords, service-account JSON,
API keys) before they're persisted."""

from __future__ import annotations

from typing import Any, Protocol


class CredentialCipher(Protocol):
    def encrypt(self, secrets: dict[str, Any]) -> str:
        """Serialize and encrypt a secrets dict into an opaque string."""
        ...

    def decrypt(self, ciphertext: str) -> dict[str, Any]:
        """Inverse of ``encrypt``. Raises on tampered/invalid ciphertext."""
        ...
