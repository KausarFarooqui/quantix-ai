"""Local-filesystem implementation of
``application.interfaces.file_storage.FileStorage``.

Deliberately simple (and swappable — see the port docstring): production
deployments serving multiple API replicas need shared storage, so this
should become an S3/GCS-backed implementation behind the same interface
before going multi-instance. Tracked in ADR-0003.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from uuid import UUID


class LocalFileStorage:
    def __init__(self, *, base_dir: str) -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, *, tenant_id: UUID, filename: str, content: bytes) -> str:
        tenant_dir = self._base_dir / str(tenant_id)
        tenant_dir.mkdir(parents=True, exist_ok=True)
        # Prefix with a UUID so two uploads of "sales.csv" never collide,
        # while keeping the original name visible for operators.
        safe_name = f"{uuid.uuid4()}_{Path(filename).name}"
        path = tenant_dir / safe_name
        path.write_bytes(content)
        return str(path)

    def read(self, *, storage_path: str) -> bytes:
        return Path(storage_path).read_bytes()

    def delete(self, *, storage_path: str) -> None:
        path = Path(storage_path)
        if path.exists():
            path.unlink()
