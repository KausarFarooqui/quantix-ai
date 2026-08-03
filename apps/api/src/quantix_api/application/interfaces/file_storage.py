"""Port for storing raw uploaded files prior to parsing.

Kept separate from ``DatasetStorage``: this holds the *original* uploaded
bytes (so a CSV can be re-parsed later, e.g. after a schema-inference bug
fix), while ``DatasetStorage`` holds the *materialized, parsed* Parquet
output. Different lifecycle, different retention story — some deployments
may want to discard raw files after ingestion but keep the Parquet.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class FileStorage(Protocol):
    def save(self, *, tenant_id: UUID, filename: str, content: bytes) -> str:
        """Persist raw file bytes. Returns a storage path/URI."""
        ...

    def read(self, *, storage_path: str) -> bytes:
        ...

    def delete(self, *, storage_path: str) -> None:
        ...
