"""Data connector layer: data_sources, datasets, and new audit_action values.

Revision ID: 202608040001
Revises: 202608030001
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202608040001"
down_revision: str | None = "202608030001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# create_type=False on the TYPE object (not as a sa.Column kwarg — that's
# silently ignored, see 202608030001's comment) is what stops
# op.create_table's before_create DDL event from re-issuing CREATE TYPE
# for a type the checkfirst loop in upgrade() already created.
source_type_enum = postgresql.ENUM(
    "csv",
    "excel",
    "json",
    "parquet",
    "postgresql",
    "mysql",
    "sql_server",
    "sqlite",
    "snowflake",
    "bigquery",
    "google_sheets",
    name="source_type",
    create_type=False,
)
data_source_status_enum = postgresql.ENUM(
    "pending", "active", "error", name="data_source_status", create_type=False
)
dataset_status_enum = postgresql.ENUM(
    "pending", "processing", "ready", "failed", name="dataset_status", create_type=False
)

_ENUMS = (source_type_enum, data_source_status_enum, dataset_status_enum)

# New AuditAction members added in this milestone (domain/entities/audit_log.py).
_NEW_AUDIT_ACTIONS = (
    "data_source.created",
    "data_source.connection_tested",
    "data_source.deleted",
    "dataset.ingested",
    "dataset.ingestion_failed",
    "dataset.deleted",
)


def upgrade() -> None:
    bind = op.get_bind()

    # ALTER TYPE ... ADD VALUE is transaction-safe on Postgres 12+ as long
    # as the new value isn't *used* in the same transaction — which this
    # migration doesn't do, it only adds the labels.
    for value in _NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{value}'")

    for enum_type in _ENUMS:
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "data_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_type", source_type_enum, nullable=False),
        sa.Column(
            "config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"
        ),
        sa.Column("encrypted_secrets", sa.Text(), nullable=True),
        sa.Column("status", data_source_status_enum, nullable=False, server_default="pending"),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_error", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_data_sources_created_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_data_sources"),
    )
    op.create_index("ix_data_sources_tenant_id", "data_sources", ["tenant_id"])
    op.create_index("ix_data_sources_source_type", "data_sources", ["source_type"])

    op.create_table(
        "datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("data_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("table_identifier", sa.String(1000), nullable=False),
        sa.Column(
            "schema_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("row_count", sa.BigInteger(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("storage_uri", sa.String(1000), nullable=True),
        sa.Column("status", dataset_status_enum, nullable=False, server_default="pending"),
        sa.Column("status_message", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["data_source_id"],
            ["data_sources.id"],
            name="fk_datasets_data_source_id_data_sources",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_datasets"),
    )
    op.create_index("ix_datasets_tenant_id", "datasets", ["tenant_id"])
    op.create_index("ix_datasets_data_source_id", "datasets", ["data_source_id"])


def downgrade() -> None:
    op.drop_table("datasets")
    op.drop_table("data_sources")

    bind = op.get_bind()
    for enum_type in reversed(_ENUMS):
        enum_type.drop(bind, checkfirst=True)

    # Note: Postgres does not support removing individual enum values
    # (no `ALTER TYPE ... DROP VALUE`). The `_NEW_AUDIT_ACTIONS` labels
    # added to `audit_action` in upgrade() are intentionally left in place
    # on downgrade — harmless unused labels, not a correctness issue.
