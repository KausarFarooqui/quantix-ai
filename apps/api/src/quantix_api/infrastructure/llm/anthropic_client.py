"""Anthropic implementation of ``application.interfaces.llm_client.LLMClient``.

Translates the provider-agnostic ``LLMMessage``/``ToolSpec`` shapes into
the Anthropic Messages API's content-block protocol (tool use lives on
the assistant turn, tool results are a block on the following user turn)
and back — this is the one place in the codebase that knows that shape.
"""

from __future__ import annotations

import time

import anthropic

from quantix_api.application.interfaces.llm_client import (
    LLMMessage,
    LLMResponse,
    LLMToolCall,
    LLMUsage,
    ToolChoice,
    ToolSpec,
)
from quantix_api.domain.exceptions.agents import LLMProviderError

_TOOL_CHOICE_MAP: dict[ToolChoice, dict[str, str]] = {
    "auto": {"type": "auto"},
    "any": {"type": "any"},
    "none": {"type": "none"},
}


class AnthropicLLMClient:
    """Note: the underlying SDK client is constructed lazily, on first
    use, not in ``__init__`` — this is a process-wide singleton built at
    app startup (see ``core.container``), and startup should not depend
    on ``anthropic_api_key`` being configured yet (mirrors how OAuth
    provider clients in milestone 2 are simply absent, rather than
    present-but-broken, when unconfigured).
    """

    def __init__(self, *, api_key: str, model: str, request_timeout_seconds: float = 60.0) -> None:
        self._api_key = api_key
        self._model = model
        self._request_timeout_seconds = request_timeout_seconds
        self._client: anthropic.AsyncAnthropic | None = None

    def _get_client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(
                api_key=self._api_key, timeout=self._request_timeout_seconds
            )
        return self._client

    async def complete(
        self,
        *,
        messages: list[LLMMessage],
        system: str,
        tools: list[ToolSpec] | None = None,
        tool_choice: ToolChoice = "auto",
        max_tokens: int = 4096,
    ) -> LLMResponse:
        kwargs: dict = {
            "model": self._model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [_to_anthropic_message(m) for m in messages],
        }
        if tools:
            kwargs["tools"] = [_to_anthropic_tool(t) for t in tools]
            kwargs["tool_choice"] = _TOOL_CHOICE_MAP[tool_choice]

        started = time.monotonic()
        try:
            response = await self._get_client().messages.create(**kwargs)
        except anthropic.APIError as exc:
            raise LLMProviderError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 — network/serialization failures, all fatal to this call
            raise LLMProviderError(f"unexpected error calling Anthropic: {exc}") from exc
        _ = time.monotonic() - started  # available to callers that want latency; agents time their own span

        text_parts: list[str] = []
        tool_calls: list[LLMToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    LLMToolCall(id=block.id, name=block.name, arguments=dict(block.input))
                )

        return LLMResponse(
            text="".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            usage=LLMUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
            ),
            stop_reason=response.stop_reason,
        )


def _to_anthropic_tool(tool: ToolSpec) -> dict:
    return {"name": tool.name, "description": tool.description, "input_schema": tool.parameters}


def _to_anthropic_message(message: LLMMessage) -> dict:
    if message.role == "tool":
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id,
                    "content": message.content,
                }
            ],
        }

    if message.role == "assistant" and message.tool_calls:
        content: list[dict] = []
        if message.content:
            content.append({"type": "text", "text": message.content})
        content.extend(
            {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}
            for call in message.tool_calls
        )
        return {"role": "assistant", "content": content}

    return {"role": message.role, "content": message.content}
