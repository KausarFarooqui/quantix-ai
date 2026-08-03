"""Supervisor node — the router at the center of the agent graph.

Every conversation turn starts (and, after each specialized agent runs,
returns) here. The supervisor's only job is a forced tool call: either
``route_to_agent`` (hand off to one specialist, possibly again after a
prior one already ran) or ``finish`` (the turn is answered — respond with
this text). Forcing the decision through a tool call (``tool_choice="any"``)
rather than parsing free text keeps routing reliable — there's no "the
model said something routing-shaped but not quite matching an agent name"
failure mode to handle.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

from quantix_api.application.interfaces.agent_graph import (
    AgentRunContext,
    AgentRunResult,
    AgentState,
)
from quantix_api.application.interfaces.llm_client import LLMClient, LLMMessage, ToolSpec
from quantix_api.domain.entities.agent_run import AgentRunStatus, AgentType
from quantix_api.infrastructure.agents.configs import ROUTING_DESCRIPTIONS

_SYSTEM_PROMPT_TEMPLATE = (
    "You are the supervisor of a multi-agent data analytics system called Quantix AI. Given the "
    "conversation so far and what's already been produced this turn, decide what happens next: "
    "either route to one specialist agent to do more work, or finish the turn with a response to "
    "the user.\n\n"
    "Available agents:\n{agent_list}\n\n"
    "{dataset_status}\n\n"
    "Guidance: route to exactly the agents needed to answer the request, not every agent that "
    "could plausibly help. Most turns need only one specialist. Once you have enough to answer, "
    "call finish with a complete, well-written response synthesizing what the specialists found — "
    "don't just repeat an agent's raw output verbatim if it needs framing for the user."
)

_ROUTE_TOOL = ToolSpec(
    name="route_to_agent",
    description="Hand this turn off to one specialist agent to do more work.",
    parameters={
        "type": "object",
        "properties": {
            "agent_type": {"type": "string", "enum": [t.value for t in ROUTING_DESCRIPTIONS]},
            "instructions": {
                "type": "string",
                "description": "What this agent should specifically do or answer.",
            },
        },
        "required": ["agent_type"],
    },
)

_FINISH_TOOL = ToolSpec(
    name="finish",
    description="End this turn and respond to the user.",
    parameters={
        "type": "object",
        "properties": {"response": {"type": "string"}},
        "required": ["response"],
    },
)


@dataclass(frozen=True, slots=True)
class SupervisorDecision:
    run_result: AgentRunResult
    next_agent: AgentType | None
    finished: bool
    final_response: str | None


class SupervisorNode:
    def __init__(self, *, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    async def decide(self, *, state: AgentState, context: AgentRunContext) -> SupervisorDecision:
        started = time.monotonic()

        if state.iterations >= context.max_iterations:
            return SupervisorDecision(
                run_result=AgentRunResult(
                    agent_type=AgentType.SUPERVISOR,
                    status=AgentRunStatus.SUCCEEDED,
                    output_summary="iteration limit reached",
                    latency_ms=int((time.monotonic() - started) * 1000),
                ),
                next_agent=None,
                finished=True,
                final_response=(
                    "I've gathered what I can for this turn — happy to keep going if you tell me "
                    "more specifically what you'd like next."
                ),
            )

        try:
            messages = [LLMMessage(role=turn.role, content=turn.content) for turn in state.history]
            if state.agent_outputs:
                messages.append(
                    LLMMessage(
                        role="user",
                        content="[System note: findings produced so far this turn: "
                        f"{json.dumps(state.agent_outputs, default=str)[:4000]}]",
                    )
                )
            response = await self._llm_client.complete(
                messages=messages,
                system=_build_system_prompt(context),
                tools=[_ROUTE_TOOL, _FINISH_TOOL],
                tool_choice="any",
                max_tokens=512,
            )
        except Exception as exc:  # noqa: BLE001 — the turn ends gracefully, not with a 500
            return SupervisorDecision(
                run_result=AgentRunResult(
                    agent_type=AgentType.SUPERVISOR,
                    status=AgentRunStatus.FAILED,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    error_message=str(exc),
                ),
                next_agent=None,
                finished=True,
                final_response="Something went wrong routing your request — please try again.",
            )

        latency_ms = int((time.monotonic() - started) * 1000)
        usage_kwargs = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
        }

        if not response.tool_calls:
            return SupervisorDecision(
                run_result=AgentRunResult(
                    agent_type=AgentType.SUPERVISOR,
                    status=AgentRunStatus.SUCCEEDED,
                    output_summary="finished (no tool call)",
                    latency_ms=latency_ms,
                    **usage_kwargs,
                ),
                next_agent=None,
                finished=True,
                final_response=response.text or "I'm not sure how to help with that — could you rephrase?",
            )

        call = response.tool_calls[0]
        if call.name == "finish":
            reply = call.arguments.get("response") or "Done."
            return SupervisorDecision(
                run_result=AgentRunResult(
                    agent_type=AgentType.SUPERVISOR,
                    status=AgentRunStatus.SUCCEEDED,
                    output_summary="finished",
                    latency_ms=latency_ms,
                    **usage_kwargs,
                ),
                next_agent=None,
                finished=True,
                final_response=reply,
            )

        agent_type_value = call.arguments.get("agent_type")
        try:
            next_agent = AgentType(agent_type_value)
            if next_agent not in ROUTING_DESCRIPTIONS:
                raise ValueError(agent_type_value)
        except ValueError:
            return SupervisorDecision(
                run_result=AgentRunResult(
                    agent_type=AgentType.SUPERVISOR,
                    status=AgentRunStatus.FAILED,
                    latency_ms=latency_ms,
                    error_message=f"Model requested unknown agent '{agent_type_value}'",
                    **usage_kwargs,
                ),
                next_agent=None,
                finished=True,
                final_response="I had trouble figuring out how to route your request — could you rephrase it?",
            )

        return SupervisorDecision(
            run_result=AgentRunResult(
                agent_type=AgentType.SUPERVISOR,
                status=AgentRunStatus.SUCCEEDED,
                output_summary=f"routed to {next_agent.value}",
                latency_ms=latency_ms,
                **usage_kwargs,
            ),
            next_agent=next_agent,
            finished=False,
            final_response=None,
        )


def _build_system_prompt(context: AgentRunContext) -> str:
    agent_list = "\n".join(
        f"- {agent_type.value}: {description}" for agent_type, description in ROUTING_DESCRIPTIONS.items()
    )
    if context.dataset is not None:
        dataset_status = (
            f"A dataset ('{context.dataset.name}', status={context.dataset.status.value}) is "
            "attached to this conversation."
        )
    else:
        dataset_status = (
            "No dataset is currently attached to this conversation — data_ingestion is the only "
            "agent that can act meaningfully until one is."
        )
    return _SYSTEM_PROMPT_TEMPLATE.format(agent_list=agent_list, dataset_status=dataset_status)
