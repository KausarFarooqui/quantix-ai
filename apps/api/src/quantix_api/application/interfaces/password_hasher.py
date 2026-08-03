"""Port for password hashing — implemented by ``infrastructure.security``."""

from __future__ import annotations

from typing import Protocol


class PasswordHasher(Protocol):
    def hash(self, plain_password: str) -> str:
        """Hash a plaintext password for storage."""
        ...

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        """Return True iff ``plain_password`` matches ``hashed_password``."""
        ...

    def needs_rehash(self, hashed_password: str) -> bool:
        """Return True if the stored hash was made with outdated
        parameters and should be regenerated on next successful login.
        """
        ...
