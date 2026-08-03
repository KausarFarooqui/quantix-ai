"""AgentRun domain entity — one execution record for a single specialized
agent within a conversation turn. Exists mainly for observability/cost
accounting (which agent ran, how long, how many tokens, did it fail) —
the actual conversational content lives on ``Message``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

from quantix_api.domain.entities.base import TenantScopedEntity


class AgentType(StrEnum):
    """The twelve specialized agents Quantix orchestrates. Adding a
    thirteenth is a two-step process: add the member here, and register a
    node for it in ``infrastructure.agents.graph`` (see ADR-0004).
    """

    SUPERVISOR = "supervisor"  # the router itself — recorded for observability, never user-facing
    DATA_INGESTION = "data_ingestion"
    DATA_PROFILING = "data_profiling"
    DATA_CLEANING = "data_cleaning"
    SQL_GENERATION = "sql_generation"
    PYTHON_ANALYSIS = "python_analysis"
    VISUALIZATION = "visualization"
    FORECASTING = "forecasting"
    AUTOML = "automl"
    RECOMMENDATION = "recommendation"
    EXECUTIVE_REPORT = "executive_report"
    DASHBOARD_BUILDER = "dashboard_builder"
    EXPLAINABLE_AI = "explainable_ai"


class AgentRunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(kw_only=True, eq=False)  # see base.Entity docstring — required to inherit identity equality
class AgentRun(TenantScopedEntity):
    """A single specialized-agent invocation, one row per node execution
    in the LangGraph run that produced (or contributed to) a Message.
    """

    conversation_id: UUID
    message_id: UUID | None = None  # set once the turn's assistant Message is persisted
    agent_type: AgentType
    status: AgentRunStatus = AgentRunStatus.RUNNING
    input_summary: str | None = None
    output_summary: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: int | None = None
    error_message: str | None = None

    def mark_succeeded(
        self, *, output_summary: str, prompt_tokens: int, completion_tokens: int, latency_ms: int
    ) -> None:
        self.status = AgentRunStatus.SUCCEEDED
        self.output_summary = output_summary
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.latency_ms = latency_ms

    def mark_failed(self, *, error_message: str, latency_ms: int) -> None:
        self.status = AgentRunStatus.FAILED
        self.error_message = error_message
        self.latency_ms = latency_ms
