"""Port for talking to a large language model — every agent node goes
through this rather than importing an LLM SDK directly, so the model
provider (Anthropic today) is swappable and agent logic is testable
against a scripted fake with no network calls.

Shaped around a single-turn "complete" call with optional tool-calling
rather than a chat-session object, because that's the actual unit of work
every agent node needs: give me a response (text and/or tool calls) for
this message history. Multi-turn tool loops (call a tool, feed the result
back, call again) are the *agent's* responsibility
(``infrastructure.agents.prompted_agent``), not this port's — keeping the
port minimal keeps it easy to fake in tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass(frozen=True, slots=True)
class LLMToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class LLMMessage:
    """One turn in the message history sent to the model. ``role`` is
    ``"user"``, ``"assistant"``, or ``"tool"`` (a tool result being fed
    back in) — deliberately not the domain's ``MessageRole``, since tool
    turns have no equivalent there.

    ``tool_calls`` is set on an ``"assistant"`` turn that requested tool
    use, so a provider client can faithfully reconstruct the
    request/result round-trip its API expects (Anthropic, for instance,
    represents a tool call as part of the assistant turn and the result as
    a block on the *next* user turn) — carrying it here keeps that
    provider-specific reconstruction out of agent code, which only ever
    speaks in ``LLMMessage``.
    """

    role: Literal["user", "assistant", "tool"]
    content: str
    tool_call_id: str | None = None  # set when role == "tool"
    tool_name: str | None = None  # set when role == "tool"
    tool_calls: tuple[LLMToolCall, ...] | None = None  # set when role == "assistant"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """A tool the model may call — name, description, and a JSON Schema
    for its arguments. Execution is not part of this port: the agent node
    that offers the tool is the one that runs it.
    """

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True, slots=True)
class LLMUsage:
    prompt_tokens: int
    completion_tokens: int


@dataclass(frozen=True, slots=True)
class LLMResponse:
    text: str | None
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    usage: LLMUsage = field(default_factory=lambda: LLMUsage(prompt_tokens=0, completion_tokens=0))
    stop_reason: str | None = None


ToolChoice = Literal["auto", "any", "none"]


class LLMClient(Protocol):
    async def complete(
        self,
        *,
        messages: list[LLMMessage],
        system: str,
        tools: list[ToolSpec] | None = None,
        tool_choice: ToolChoice = "auto",
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Request one completion. ``tool_choice="any"`` forces the model
        to call one of ``tools`` rather than reply in plain text — used by
        the supervisor, where "just talk instead of routing" isn't a
        valid outcome.
        """
        ...
