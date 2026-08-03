"""Audit log domain entity.

Append-only record of security-relevant events. Deliberately permissive
about `metadata` (a JSON-serializable dict) rather than a rigid schema per
event type — new event types shouldn't require a migration to record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

from quantix_api.domain.entities.base import Entity


class AuditAction(StrEnum):
    TENANT_CREATED = "tenant.created"
    USER_REGISTERED = "user.registered"
    USER_LOGIN_SUCCEEDED = "user.login_succeeded"
    USER_LOGIN_FAILED = "user.login_failed"
    USER_LOGGED_OUT = "user.logged_out"
    USER_OAUTH_LOGIN_SUCCEEDED = "user.oauth_login_succeeded"
    USER_OAUTH_LINK_FAILED = "user.oauth_link_failed"
    TOKEN_REFRESHED = "token.refreshed"
    TOKEN_REUSE_DETECTED = "token.reuse_detected"
    USER_ROLE_CHANGED = "user.role_changed"
    DATA_SOURCE_CREATED = "data_source.created"
    DATA_SOURCE_CONNECTION_TESTED = "data_source.connection_tested"
    DATA_SOURCE_DELETED = "data_source.deleted"
    DATASET_INGESTED = "dataset.ingested"
    DATASET_INGESTION_FAILED = "dataset.ingestion_failed"
    DATASET_DELETED = "dataset.deleted"
    CONVERSATION_STARTED = "conversation.started"
    AGENT_TURN_COMPLETED = "agent_turn.completed"
    AGENT_TURN_FAILED = "agent_turn.failed"


@dataclass(kw_only=True, eq=False)  # see base.Entity docstring — required to inherit identity equality
class AuditLog(Entity):
    """A single immutable audit trail entry."""

    tenant_id: UUID | None  # None for pre-tenant events (e.g. failed login by unknown email)
    actor_user_id: UUID | None
    action: AuditAction
    resource_type: str | None = None
    resource_id: str | None = None
    ip_address: str | None = None
    metadata_: dict[str, Any] = field(default_factory=dict)
