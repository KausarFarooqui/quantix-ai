"""Argon2id password hashing — implements ``application.interfaces.password_hasher.PasswordHasher``."""

from __future__ import annotations

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class Argon2PasswordHasher:
    """Argon2id via passlib. Argon2 is the OWASP-recommended default for
    new applications (memory-hard, resistant to GPU cracking).
    """

    def hash(self, plain_password: str) -> str:
        return _pwd_context.hash(plain_password)

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        return _pwd_context.verify(plain_password, hashed_password)

    def needs_rehash(self, hashed_password: str) -> bool:
        return _pwd_context.needs_update(hashed_password)
