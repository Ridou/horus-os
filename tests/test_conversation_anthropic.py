"""Tests for the Anthropic Conversation class."""

from __future__ import annotations

import sys
import types
from typing import Any, ClassVar

import pytest

from horus_os._providers import _anthropic
from horus_os.types import Tool, ToolResult


class _Block:
    def __init__(self, **fields: Any) -> None:
        for key, value in fields.items():
            setattr(self, key, value)


class _Response:
    def __init__(self, content: list[_Block]) -> None:
        self.content = content
        self.usage = None


class _FakeAnthropic:
    requests: ClassVar[list[dict[str, Any]]] = []
    responses: ClassVar[list[_Response]] = []

    def __init__(self, *_: Any, **__: Any) -> None:
        self.messages = self

    def create(self, **kwargs: Any) -> _Response:
        _FakeAnthropic.requests.append(kwargs)
        if not _FakeAnthropic.responses:
            raise RuntimeError("no scripted response left")
        return _FakeAnthropic.responses.pop(0)


@pytest.fixture
def fake_anthropic(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    module = types.ModuleType("anthropic")
    module.Anthropic = _FakeAnthropic  # type: ignore[attr-defined]
    module.AsyncAnthropic = _FakeAnthropic  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "anthropic", module)
    _FakeAnthropic.requests = []
    _FakeAnthropic.responses = []
    return module


def test_conversation_initial_prompt_sends_user_message(fake_anthropic) -> None:
    _FakeAnthropic.responses = [_Response([_Block(type="text", text="hi")])]
    conv = _anthropic.Conversation()
    result = conv.send(prompt="hello")
    assert result.text == "hi"
    request = _FakeAnthropic.requests[0]
    assert request["messages"] == [{"role": "user", "content": "hello"}]


def test_conversation_tool_use_then_results_round_trip(fake_anthropic) -> None:
    tool_use_block = _Block(type="tool_use", id="tu_1", name="echo", input={"text": "hi"})
    text_block = _Block(type="text", text="done")
    _FakeAnthropic.responses = [
        _Response([tool_use_block]),
        _Response([text_block]),
    ]
    conv = _anthropic.Conversation()
    tool = Tool(name="echo", description="echo back", parameters={"type": "object"})

    first = conv.send(prompt="say hi", tools=[tool])
    assert first.tool_uses[0].name == "echo"

    result = ToolResult(tool_use_id="tu_1", name="echo", output="hi")
    second = conv.send(tool_results=[result], tools=[tool])
    assert second.text == "done"

    second_request = _FakeAnthropic.requests[1]
    assert second_request["messages"][1] == {"role": "assistant", "content": [tool_use_block]}
    assert second_request["messages"][2]["role"] == "user"
    assert second_request["messages"][2]["content"][0]["type"] == "tool_result"
    assert second_request["messages"][2]["content"][0]["tool_use_id"] == "tu_1"
    assert second_request["messages"][2]["content"][0]["content"] == "hi"


def test_conversation_tool_error_marks_is_error(fake_anthropic) -> None:
    tool_use_block = _Block(type="tool_use", id="tu_1", name="echo", input={})
    _FakeAnthropic.responses = [
        _Response([tool_use_block]),
        _Response([_Block(type="text", text="recovered")]),
    ]
    conv = _anthropic.Conversation()
    conv.send(prompt="hi")
    conv.send(tool_results=[ToolResult(tool_use_id="tu_1", name="echo", error="boom")])
    second_request = _FakeAnthropic.requests[1]
    block = second_request["messages"][2]["content"][0]
    assert block["is_error"] is True
    assert block["content"] == "boom"


def test_conversation_send_requires_prompt_or_results(fake_anthropic) -> None:
    conv = _anthropic.Conversation()
    with pytest.raises(ValueError, match="requires either prompt or tool_results"):
        conv.send()


def test_conversation_send_rejects_both(fake_anthropic) -> None:
    conv = _anthropic.Conversation()
    with pytest.raises(ValueError, match="accepts prompt or tool_results"):
        conv.send(prompt="hi", tool_results=[])


def test_conversation_passes_tools_through(fake_anthropic) -> None:
    _FakeAnthropic.responses = [_Response([_Block(type="text", text="ok")])]
    tool = Tool(name="echo", description="d", parameters={"type": "object"})
    _anthropic.Conversation().send(prompt="hi", tools=[tool])
    request = _FakeAnthropic.requests[0]
    assert request["tools"] == [
        {"name": "echo", "description": "d", "input_schema": {"type": "object"}}
    ]
