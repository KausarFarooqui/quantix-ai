"""Fernet-based implementation of
``application.interfaces.credential_cipher.CredentialCipher``.

Fernet (AES-128-CBC + HMAC-SHA256, from the `cryptography` package) is
authenticated encryption — tampering with ciphertext is detected on
decrypt, not silently accepted. Good fit for "small secret blob at rest,"
which is exactly what connector credentials are.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class FernetCredentialCipher:
    def __init__(self, *, encryption_key: str) -> None:
        # Fernet requires a 32-byte urlsafe-base64 key; derive one
        # deterministically from the configured secret so operators don't
        # need to separately generate and store a Fernet-formatted key.
        digest = hashlib.sha256(encryption_key.encode("utf-8")).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, secrets: dict[str, Any]) -> str:
        payload = json.dumps(secrets, separators=(",", ":")).encode("utf-8")
        return self._fernet.encrypt(payload).decode("utf-8")

    def decrypt(self, ciphertext: str) -> dict[str, Any]:
        try:
            payload = self._fernet.decrypt(ciphertext.encode("utf-8"))
        except InvalidToken as exc:
            raise ValueError("Credential ciphertext is invalid, tampered with, or expired") from exc
        return json.loads(payload)
