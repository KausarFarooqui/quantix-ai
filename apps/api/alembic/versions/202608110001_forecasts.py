"""Forecasts table and new audit_action value.

Revision ID: 202608110001
Revises: 202608050001
Create Date: 2026-08-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202608110001"
down_revision: str | None = "202608050001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

forecast_method_enum = postgresql.ENUM(
    "holt_winters", "linear_trend", name="forecast_method", create_type=False
)

# New AuditAction member added in this milestone (domain/entities/audit_log.py).
_NEW_AUDIT_ACTIONS = ("forecast.generated",)


def upgrade() -> None:
    bind = op.get_bind()

    for value in _NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{value}'")

    forecast_method_enum.create(bind, checkfirst=True)

    op.create_table(
        "forecasts",
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
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_column", sa.String(255), nullable=False),
        sa.Column("time_column", sa.String(255), nullable=True),
        sa.Column("method", forecast_method_enum, nullable=False),
        sa.Column("historical_points", sa.Integer(), nullable=False),
        sa.Column(
            "points_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["datasets.id"], name="fk_forecasts_dataset_id_datasets", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_forecasts_created_by_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="fk_forecasts_conversation_id_conversations",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_forecasts"),
    )
    op.create_index("ix_forecasts_tenant_id", "forecasts", ["tenant_id"])
    op.create_index("ix_forecasts_dataset_id", "forecasts", ["dataset_id"])
    op.create_index("ix_forecasts_conversation_id", "forecasts", ["conversation_id"])


def downgrade() -> None:
    op.drop_table("forecasts")

    bind = op.get_bind()
    forecast_method_enum.drop(bind, checkfirst=True)

    # Note: Postgres does not support removing individual enum values.
    # The `_NEW_AUDIT_ACTIONS` labels added to `audit_action` in upgrade()
    # are intentionally left in place on downgrade — harmless unused
    # labels, not a correctness issue (same rationale as prior migrations'
    # downgrade()).
