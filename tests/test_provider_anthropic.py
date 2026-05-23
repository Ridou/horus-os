"""Anthropic provider tests.

Replace the `anthropic` SDK client classes at the `horus_os._providers._anthropic`
module import site so no real client is ever constructed and no API key is required.
"""

from __future__ import annotations

import asyncio
import sys
import types
from typing import Any

import pytest

from horus_os._providers import _anthropic
from horus_os.types import Tool


class _Block:
    def __init__(self, **fields: Any) -> None:
        for key, value in fields.items():
            setattr(self, key, value)


class _Usage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _Response:
    def __init__(self, content: list[_Block], usage: _Usage | None = None) -> None:
        self.content = content
        self.usage = usage


class _FakeAnthropic:
    last_request: dict[str, Any] | None = None
    next_response: _Response | None = None

    def __init__(self, *_: Any, **__: Any) -> None:
        self.messages = self

    def create(self, **kwargs: Any) -> _Response:
        _FakeAnthropic.last_request = kwargs
        return _FakeAnthropic.next_response  # type: ignore[return-value]


class _FakeAsyncAnthropic:
    last_request: dict[str, Any] | None = None
    next_response: _Response | None = None

    def __init__(self, *_: Any, **__: Any) -> None:
        self.messages = self

    async def create(self, **kwargs: Any) -> _Response:
        _FakeAsyncAnthropic.last_request = kwargs
        return _FakeAsyncAnthropic.next_response  # type: ignore[return-value]


@pytest.fixture
def fake_anthropic_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    """Install a fake `anthropic` module into sys.modules for the duration of a test."""
    module = types.ModuleType("anthropic")
    module.Anthropic = _FakeAnthropic  # type: ignore[attr-defined]
    module.AsyncAnthropic = _FakeAsyncAnthropic  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "anthropic", module)
    _FakeAnthropic.last_request = None
    _FakeAnthropic.next_response = None
    _FakeAsyncAnthropic.last_request = None
    _FakeAsyncAnthropic.next_response = None
    return module


def test_text_response_returns_agent_result(fake_anthropic_module: types.ModuleType) -> None:
    _FakeAnthropic.next_response = _Response(
        content=[_Block(type="text", text="hello world")],
        usage=_Usage(input_tokens=3, output_tokens=2),
    )
    result = _anthropic.call_anthropic("hi")
    assert result.provider == "anthropic"
    assert result.model == "claude-sonnet-4-6"
    assert result.text == "hello world"
    assert result.tool_uses == []
    assert result.usage == {"input_tokens": 3, "output_tokens": 2}


def test_tool_use_response_is_captured(fake_anthropic_module: types.ModuleType) -> None:
    _FakeAnthropic.next_response = _Response(
        content=[
            _Block(type="text", text="calling tool"),
            _Block(
                type="tool_use",
                id="tu_1",
                name="echo",
                input={"text": "hi"},
            ),
        ],
    )
    tool = Tool(name="echo", description="echo back", parameters={"type": "object"})
    result = _anthropic.call_anthropic("say hi", tools=[tool])
    assert result.text == "calling tool"
    assert len(result.tool_uses) == 1
    use = result.tool_uses[0]
    assert use.id == "tu_1"
    assert use.name == "echo"
    assert use.input == {"text": "hi"}
    request = _FakeAnthropic.last_request
    assert request is not None
    assert request["tools"] == [
        {"name": "echo", "description": "echo back", "input_schema": {"type": "object"}}
    ]


def test_default_model_can_be_overridden(fake_anthropic_module: types.ModuleType) -> None:
    _FakeAnthropic.next_response = _Response(content=[_Block(type="text", text="ok")])
    result = _anthropic.call_anthropic("hi", model="claude-haiku-4-5-20251001")
    assert result.model == "claude-haiku-4-5-20251001"
    request = _FakeAnthropic.last_request
    assert request is not None
    assert request["model"] == "claude-haiku-4-5-20251001"


def test_async_call_returns_agent_result(fake_anthropic_module: types.ModuleType) -> None:
    _FakeAsyncAnthropic.next_response = _Response(
        content=[_Block(type="text", text="hi back")],
        usage=_Usage(input_tokens=1, output_tokens=2),
    )
    result = asyncio.run(_anthropic.call_anthropic_async("hi"))
    assert result.text == "hi back"
    assert result.usage == {"input_tokens": 1, "output_tokens": 2}
