"""Generic, config-driven agent node — covers ten of the twelve agent
types (see ``configs.py``) with one class: run a bounded tool-calling
loop against the LLM using a per-agent-type system prompt and the shared
dataset tools, then return the model's final text as the agent's output.

The two agent types with a genuinely different execution model
(``AUTOML``, which trains real models, and ``DATA_INGESTION``, which
orchestrates milestone-3 use cases) get their own node classes instead —
see ``automl_agent.py`` and ``ingestion_agent.py``. This mirrors the
milestone-3 pattern of consolidating variation behind a small number of
real classes rather than one class per type (see ADR-0004).
"""

from __future__ import annotations

import json
import time

from quantix_api.application.interfaces.agent_graph import (
    AgentRunContext,
    AgentRunResult,
    AgentState,
)
from quantix_api.application.interfaces.llm_client import LLMClient, LLMMessage
from quantix_api.domain.entities.agent_run import AgentRunStatus
from quantix_api.infrastructure.agents.configs import AgentConfig
from quantix_api.infrastructure.agents.tools import ToolHandler, build_dataset_tools


class PromptedAgentNode:
    def __init__(self, *, config: AgentConfig, llm_client: LLMClient, max_tool_iterations: int = 5) -> None:
        self._config = config
        self._llm_client = llm_client
        self._max_tool_iterations = max_tool_iterations

    async def run(self, *, state: AgentState, context: AgentRunContext) -> AgentRunResult:
        started = time.monotonic()
        tools = build_dataset_tools(context) if self._config.uses_dataset_tools else []
        tool_by_name: dict[str, ToolHandler] = {t.spec.name: t for t in tools}

        messages = [LLMMessage(role=turn.role, content=turn.content) for turn in state.history]
        system_prompt = _build_system_prompt(self._config, state)

        total_prompt_tokens = 0
        total_completion_tokens = 0
        tool_call_log: list[dict] = []
        final_text: str | None = None

        try:
            for _ in range(self._max_tool_iterations):
                response = await self._llm_client.complete(
                    messages=messages,
                    system=system_prompt,
                    tools=[t.spec for t in tools] or None,
                    tool_choice="auto",
                    max_tokens=2048,
                )
                total_prompt_tokens += response.usage.prompt_tokens
                total_completion_tokens += response.usage.completion_tokens

                if not response.tool_calls:
                    final_text = response.text
                    break

                messages.append(
                    LLMMessage(
                        role="assistant",
                        content=response.text or "",
                        tool_calls=tuple(response.tool_calls),
                    )
                )
                for call in response.tool_calls:
                    handler = tool_by_name.get(call.name)
                    if handler is None:
                        result_text = f"Unknown tool '{call.name}'"
                    else:
                        result_text = await handler.call(call.arguments)
                    tool_call_log.append({"name": call.name, "arguments": call.arguments})
                    messages.append(
                        LLMMessage(
                            role="tool",
                            content=result_text,
                            tool_call_id=call.id,
                            tool_name=call.name,
                        )
                    )
            else:
                # Loop exhausted without a plain-text final answer — ask
                # once more with tools disabled so the agent is forced to
                # summarize whatever it has learned instead of looping.
                response = await self._llm_client.complete(
                    messages=messages, system=system_prompt, tools=None, max_tokens=1024
                )
                total_prompt_tokens += response.usage.prompt_tokens
                total_completion_tokens += response.usage.completion_tokens
                final_text = response.text

        except Exception as exc:  # noqa: BLE001 — converted to a FAILED AgentRunResult, not raised
            return AgentRunResult(
                agent_type=self._config.agent_type,
                status=AgentRunStatus.FAILED,
                tool_calls=tool_call_log,
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                latency_ms=int((time.monotonic() - started) * 1000),
                error_message=str(exc),
            )

        return AgentRunResult(
            agent_type=self._config.agent_type,
            status=AgentRunStatus.SUCCEEDED,
            output_summary=final_text or "(no response produced)",
            tool_calls=tool_call_log,
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            latency_ms=int((time.monotonic() - started) * 1000),
        )


def _build_system_prompt(config: AgentConfig, state: AgentState) -> str:
    prior_outputs = {k: v for k, v in state.agent_outputs.items() if k != config.agent_type.value}
    if not prior_outputs:
        return config.system_prompt
    return (
        f"{config.system_prompt}\n\n"
        "Other agents already produced this context earlier in this turn — use it instead of "
        "re-deriving it where relevant:\n"
        f"{json.dumps(prior_outputs, default=str)[:4000]}"
    )
