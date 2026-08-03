"""ORM model for data sources."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from quantix_api.domain.entities.data_source import DataSourceStatus, SourceType
from quantix_api.infrastructure.database.models.base import (
    PORTABLE_JSON,
    Base,
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class DataSourceModel(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "data_sources"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="source_type", native_enum=True), nullable=False, index=True
    )
    config: Mapped[dict] = mapped_column(PORTABLE_JSON, nullable=False, default=dict)
    # Fernet ciphertext (base64) — never plaintext, never returned by the API.
    encrypted_secrets: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DataSourceStatus] = mapped_column(
        Enum(DataSourceStatus, name="data_source_status", native_enum=True),
        nullable=False,
        default=DataSourceStatus.PENDING,
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
