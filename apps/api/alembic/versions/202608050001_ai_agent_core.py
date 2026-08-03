"""AI agent core: conversations, messages, agent_runs, and new audit_action values.

Revision ID: 202608050001
Revises: 202608040001
Create Date: 2026-08-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202608050001"
down_revision: str | None = "202608040001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# create_type=False on the TYPE object (not as a sa.Column kwarg — that's
# silently ignored, see 202608030001's comment) is what stops
# op.create_table's before_create DDL event from re-issuing CREATE TYPE
# for a type the checkfirst loop in upgrade() already created.
conversation_status_enum = postgresql.ENUM(
    "active", "archived", name="conversation_status", create_type=False
)
message_role_enum = postgresql.ENUM(
    "user", "assistant", "system", name="message_role", create_type=False
)
agent_type_enum = postgresql.ENUM(
    "supervisor",
    "data_ingestion",
    "data_profiling",
    "data_cleaning",
    "sql_generation",
    "python_analysis",
    "visualization",
    "forecasting",
    "automl",
    "recommendation",
    "executive_report",
    "dashboard_builder",
    "explainable_ai",
    name="agent_type",
    create_type=False,
)
agent_run_status_enum = postgresql.ENUM(
    "running", "succeeded", "failed", name="agent_run_status", create_type=False
)

_ENUMS = (conversation_status_enum, message_role_enum, agent_type_enum, agent_run_status_enum)

# New AuditAction members added in this milestone (domain/entities/audit_log.py).
_NEW_AUDIT_ACTIONS = (
    "conversation.started",
    "agent_turn.completed",
    "agent_turn.failed",
)


def upgrade() -> None:
    bind = op.get_bind()

    for value in _NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{value}'")

    for enum_type in _ENUMS:
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "conversations",
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
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", conversation_status_enum, nullable=False, server_default="active"),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name="fk_conversations_dataset_id_datasets",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_conversations_created_by_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_conversations"),
    )
    op.create_index("ix_conversations_tenant_id", "conversations", ["tenant_id"])
    op.create_index("ix_conversations_dataset_id", "conversations", ["dataset_id"])

    op.create_table(
        "messages",
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
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", message_role_enum, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("agent_type", agent_type_enum, nullable=True),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="fk_messages_conversation_id_conversations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_messages"),
    )
    op.create_index("ix_messages_tenant_id", "messages", ["tenant_id"])
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    op.create_table(
        "agent_runs",
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
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_type", agent_type_enum, nullable=False),
        sa.Column("status", agent_run_status_enum, nullable=False, server_default="running"),
        sa.Column("input_summary", sa.Text(), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column(
            "tool_calls", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"
        ),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="fk_agent_runs_conversation_id_conversations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name="fk_agent_runs_message_id_messages",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_runs"),
    )
    op.create_index("ix_agent_runs_tenant_id", "agent_runs", ["tenant_id"])
    op.create_index("ix_agent_runs_conversation_id", "agent_runs", ["conversation_id"])
    op.create_index("ix_agent_runs_message_id", "agent_runs", ["message_id"])


def downgrade() -> None:
    op.drop_table("agent_runs")
    op.drop_table("messages")
    op.drop_table("conversations")

    bind = op.get_bind()
    for enum_type in reversed(_ENUMS):
        enum_type.drop(bind, checkfirst=True)

    # Note: Postgres does not support removing individual enum values.
    # The `_NEW_AUDIT_ACTIONS` labels added to `audit_action` in upgrade()
    # are intentionally left in place on downgrade — harmless unused
    # labels, not a correctness issue (same rationale as the prior
    # migration's downgrade()).
