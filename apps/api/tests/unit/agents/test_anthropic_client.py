"""Unit tests for ``AnthropicLLMClient`` — exercises the ``LLMMessage``/
``ToolSpec`` <-> Anthropic Messages API content-block translation against a
scripted fake standing in for ``anthropic.AsyncAnthropic``. Real network
calls to the Anthropic API are out of scope for the unit suite (see
ADR-0004); this covers everything client-side of that boundary: request
shaping, response parsing, and error translation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import anthropic
import pytest

from quantix_api.application.interfaces.llm_client import LLMMessage, LLMToolCall, ToolSpec
from quantix_api.domain.exceptions.agents import LLMProviderError
from quantix_api.infrastructure.llm.anthropic_client import AnthropicLLMClient


@dataclass
class _FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class _FakeToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]
    type: str = "tool_use"


@dataclass
class _FakeUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class _FakeAnthropicResponse:
    content: list[Any] = field(default_factory=list)
    usage: _FakeUsage = field(default_factory=lambda: _FakeUsage(0, 0))
    stop_reason: str | None = "end_turn"


class _FakeAPIError(anthropic.APIError):
    """A minimal ``anthropic.APIError`` instance for tests — bypasses the
    real SDK's ``__init__`` (which wants an ``httpx.Request``) since all
    ``AnthropicLLMClient`` needs from it is ``isinstance`` truthiness and a
    sensible ``str()``.
    """

    def __init__(self, message: str) -> None:
        Exception.__init__(self, message)
        self.message = message


class _FakeMessages:
    def __init__(self, response: _FakeAnthropicResponse | Exception) -> None:
        self._response = response
        self.last_kwargs: dict[str, Any] | None = None

    async def create(self, **kwargs: Any) -> _FakeAnthropicResponse:
        self.last_kwargs = kwargs
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class _FakeAsyncAnthropic:
    """Stand-in for ``anthropic.AsyncAnthropic``. Constructed the same way
    (``api_key``/``timeout`` kwargs) but ``.messages.create`` is scripted
    via the class-level ``next_response`` rather than making a real network
    call — set it before exercising ``AnthropicLLMClient.complete()``,
    since the SDK client is built lazily on first use.
    """

    next_response: _FakeAnthropicResponse | Exception = _FakeAnthropicResponse()
    instances: list["_FakeAsyncAnthropic"] = []

    def __init__(self, *, api_key: str, timeout: float) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.messages = _FakeMessages(_FakeAsyncAnthropic.next_response)
        _FakeAsyncAnthropic.instances.append(self)


@pytest.fixture(autouse=True)
def _reset_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeAsyncAnthropic.instances = []
    _FakeAsyncAnthropic.next_response = _FakeAnthropicResponse()
    monkeypatch.setattr(anthropic, "AsyncAnthropic", _FakeAsyncAnthropic)


def _client() -> AnthropicLLMClient:
    return AnthropicLLMClient(api_key="sk-test", model="claude-x")


class TestComplete:
    async def test_returns_text_response(self) -> None:
        _FakeAsyncAnthropic.next_response = _FakeAnthropicResponse(
            content=[_FakeTextBlock(text="hello there")],
            usage=_FakeUsage(input_tokens=12, output_tokens=4),
            stop_reason="end_turn",
        )

        response = await _client().complete(
            messages=[LLMMessage(role="user", content="hi")], system="be helpful"
        )

        assert response.text == "hello there"
        assert response.tool_calls == []
        assert response.usage.prompt_tokens == 12
        assert response.usage.completion_tokens == 4
        assert response.stop_reason == "end_turn"

    async def test_returns_tool_calls(self) -> None:
        _FakeAsyncAnthropic.next_response = _FakeAnthropicResponse(
            content=[_FakeToolUseBlock(id="call_1", name="run_sql", input={"query": "SELECT 1"})],
            usage=_FakeUsage(input_tokens=20, output_tokens=8),
            stop_reason="tool_use",
        )

        response = await _client().complete(
            messages=[LLMMessage(role="user", content="run a query")],
            system="be helpful",
            tools=[ToolSpec(name="run_sql", description="Run SQL", parameters={"type": "object"})],
            tool_choice="any",
        )

        assert response.text is None
        assert response.tool_calls == [
            LLMToolCall(id="call_1", name="run_sql", arguments={"query": "SELECT 1"})
        ]

    async def test_combines_text_and_tool_calls(self) -> None:
        _FakeAsyncAnthropic.next_response = _FakeAnthropicResponse(
            content=[
                _FakeTextBlock(text="Let me check that."),
                _FakeToolUseBlock(id="call_1", name="run_sql", input={}),
            ]
        )

        response = await _client().complete(
            messages=[LLMMessage(role="user", content="hi")], system="be helpful"
        )

        assert response.text == "Let me check that."
        assert len(response.tool_calls) == 1

    async def test_sends_tools_and_maps_tool_choice(self) -> None:
        _FakeAsyncAnthropic.next_response = _FakeAnthropicResponse()
        client = _client()

        await client.complete(
            messages=[LLMMessage(role="user", content="hi")],
            system="be helpful",
            tools=[ToolSpec(name="run_sql", description="Run SQL", parameters={"type": "object"})],
            tool_choice="none",
            max_tokens=512,
        )

        sent = _FakeAsyncAnthropic.instances[0].messages.last_kwargs
        assert sent is not None
        assert sent["max_tokens"] == 512
        assert sent["tools"] == [
            {"name": "run_sql", "description": "Run SQL", "input_schema": {"type": "object"}}
        ]
        assert sent["tool_choice"] == {"type": "none"}

    async def test_omits_tools_when_none_supplied(self) -> None:
        _FakeAsyncAnthropic.next_response = _FakeAnthropicResponse()
        client = _client()

        await client.complete(messages=[LLMMessage(role="user", content="hi")], system="be helpful")

        sent = _FakeAsyncAnthropic.instances[0].messages.last_kwargs
        assert sent is not None
        assert "tools" not in sent
        assert "tool_choice" not in sent

    async def test_translates_tool_result_message(self) -> None:
        _FakeAsyncAnthropic.next_response = _FakeAnthropicResponse()
        client = _client()

        await client.complete(
            messages=[
                LLMMessage(
                    role="tool", content="42 rows", tool_call_id="call_1", tool_name="run_sql"
                )
            ],
            system="be helpful",
        )

        sent = _FakeAsyncAnthropic.instances[0].messages.last_kwargs
        assert sent["messages"] == [
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "call_1", "content": "42 rows"}],
            }
        ]

    async def test_translates_assistant_message_with_tool_calls_and_text(self) -> None:
        _FakeAsyncAnthropic.next_response = _FakeAnthropicResponse()
        client = _client()

        await client.complete(
            messages=[
                LLMMessage(
                    role="assistant",
                    content="Let me check.",
                    tool_calls=(LLMToolCall(id="call_1", name="run_sql", arguments={"q": "x"}),),
                )
            ],
            system="be helpful",
        )

        sent = _FakeAsyncAnthropic.instances[0].messages.last_kwargs
        assert sent["messages"] == [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me check."},
                    {"type": "tool_use", "id": "call_1", "name": "run_sql", "input": {"q": "x"}},
                ],
            }
        ]

    async def test_translates_assistant_message_with_tool_calls_and_no_text(self) -> None:
        _FakeAsyncAnthropic.next_response = _FakeAnthropicResponse()
        client = _client()

        await client.complete(
            messages=[
                LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(LLMToolCall(id="call_1", name="run_sql", arguments={}),),
                )
            ],
            system="be helpful",
        )

        sent = _FakeAsyncAnthropic.instances[0].messages.last_kwargs
        assert sent["messages"] == [
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "call_1", "name": "run_sql", "input": {}}],
            }
        ]

    async def test_translates_plain_message(self) -> None:
        _FakeAsyncAnthropic.next_response = _FakeAnthropicResponse()
        client = _client()

        await client.complete(
            messages=[LLMMessage(role="user", content="hi")], system="be helpful"
        )

        sent = _FakeAsyncAnthropic.instances[0].messages.last_kwargs
        assert sent["messages"] == [{"role": "user", "content": "hi"}]

    async def test_reuses_the_same_underlying_client_across_calls(self) -> None:
        client = _client()

        await client.complete(messages=[LLMMessage(role="user", content="hi")], system="s")
        await client.complete(messages=[LLMMessage(role="user", content="hi again")], system="s")

        assert len(_FakeAsyncAnthropic.instances) == 1

    async def test_api_error_is_translated_to_llm_provider_error(self) -> None:
        _FakeAsyncAnthropic.next_response = _FakeAPIError("rate limited")

        with pytest.raises(LLMProviderError, match="rate limited"):
            await _client().complete(messages=[LLMMessage(role="user", content="hi")], system="s")

    async def test_unexpected_error_is_translated_to_llm_provider_error(self) -> None:
        _FakeAsyncAnthropic.next_response = RuntimeError("socket exploded")

        with pytest.raises(LLMProviderError, match="unexpected error calling Anthropic"):
            await _client().complete(messages=[LLMMessage(role="user", content="hi")], system="s")
