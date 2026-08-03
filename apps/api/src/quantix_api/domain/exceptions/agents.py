"""Domain exceptions for the AI agent orchestration layer."""

from __future__ import annotations

from quantix_api.domain.exceptions.base import DomainError


class AgentError(DomainError):
    """Base class for anything that goes wrong running the agent graph."""


class UnknownAgentTypeError(AgentError):
    def __init__(self, agent_type: str) -> None:
        self.agent_type = agent_type
        super().__init__(f"No agent node is registered for agent type '{agent_type}'")


class AgentExecutionError(AgentError):
    """An agent node raised while doing its work (LLM call failed, tool
    call failed and couldn't be recovered, etc.) — the conversation turn
    could not be completed.
    """

    def __init__(self, agent_type: str, reason: str) -> None:
        self.agent_type = agent_type
        self.reason = reason
        super().__init__(f"Agent '{agent_type}' failed: {reason}")


class AgentIterationLimitExceededError(AgentError):
    """The supervisor kept routing to agents without finishing — a
    circuit breaker against runaway loops (and runaway LLM spend).
    """

    def __init__(self, max_iterations: int) -> None:
        self.max_iterations = max_iterations
        super().__init__(f"Agent graph did not finish within {max_iterations} iterations")


class LLMProviderError(AgentError):
    """The underlying LLM API call failed (network, rate limit, auth)."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"LLM provider error: {reason}")


class ConversationNotActiveError(AgentError):
    def __init__(self, conversation_id: object) -> None:
        self.conversation_id = conversation_id
        super().__init__(f"Conversation {conversation_id!r} is archived and cannot accept messages")
