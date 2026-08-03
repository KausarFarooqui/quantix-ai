"""SQLAlchemy declarative base and reusable ORM mixins.

Only ``infrastructure.database`` (and ``interface`` for framework wiring)
may import SQLAlchemy — domain and application layers stay ORM-agnostic.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, MetaData, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Portable JSON: native JSONB on PostgreSQL, generic (TEXT-backed) JSON on
# dialects without one — shared by every model with a loose-schema column
# (audit log metadata, connector config, dataset schema snapshots) so the
# cross-dialect trade-off is made once, not per-model.
PORTABLE_JSON = JSON().with_variant(JSONB(astext_type=String()), "postgresql")

# Explicit naming convention: Alembic autogenerate produces stable,
# predictable constraint names instead of dialect-default garbage.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # `Uuid` is SQLAlchemy 2.0's cross-dialect UUID type: native UUID on
    # PostgreSQL, CHAR(32)/hex on dialects without one (e.g. SQLite, used
    # in the fast unit-test suite). Using the Postgres-specific
    # `postgresql.UUID` here would make every model untestable without a
    # real Postgres instance.
    type_annotation_map: dict[type, Any] = {
        uuid.UUID: Uuid(as_uuid=True, native_uuid=True),
    }


class UUIDPrimaryKeyMixin:
    """Adds a UUIDv4 primary key column."""

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, insert_sentinel=False
    )


class TimestampMixin:
    """Adds server-managed ``created_at`` / ``updated_at`` columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TenantScopedMixin:
    """Adds the ``tenant_id`` foreign key every multi-tenant table needs.

    Indexed because virtually every query filters on it — omitting the
    index would force a sequential scan per tenant on any sizeable table.
    """

    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
