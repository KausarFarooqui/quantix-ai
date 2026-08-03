"""ORM model for datasets."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from quantix_api.domain.entities.dataset import DatasetStatus
from quantix_api.infrastructure.database.models.base import (
    PORTABLE_JSON,
    Base,
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class DatasetModel(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "datasets"

    data_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    table_identifier: Mapped[str] = mapped_column(String(1000), nullable=False)
    # Serialized list[{"name", "data_type", "nullable"}] — named `schema_json`
    # (not `schema`) to avoid any ambiguity with SQLAlchemy's own use of
    # `schema` for DB namespace/Table(schema=...).
    schema_json: Mapped[list] = mapped_column(PORTABLE_JSON, nullable=False, default=list)
    row_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    storage_uri: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[DatasetStatus] = mapped_column(
        Enum(DatasetStatus, name="dataset_status", native_enum=True),
        nullable=False,
        default=DatasetStatus.PENDING,
    )
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
