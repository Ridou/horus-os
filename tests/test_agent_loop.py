"""Tests for run_agent_loop."""

from __future__ import annotations

import pytest

from horus_os import (
    AgentResult,
    Tool,
    ToolRegistry,
    ToolUse,
    run_agent_loop,
)
from horus_os._providers import _anthropic, _gemini


class _FakeConversation:
    def __init__(self, scripted: list[AgentResult]) -> None:
        self._scripted = list(scripted)
        self.calls: list[dict] = []

    def send(self, **kwargs) -> AgentResult:
        self.calls.append(kwargs)
        if not self._scripted:
            raise AssertionError("FakeConversation ran out of scripted responses")
        return self._scripted.pop(0)


def _result(*, text: str = "", tool_uses: list[ToolUse] | None = None) -> AgentResult:
    return AgentResult(
        text=text,
        tool_uses=tool_uses or [],
        provider="anthropic",
        model="claude-sonnet-4-6",
        usage={},
    )


def _registry(handler) -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(
        Tool(name="echo", description="echo", parameters={"type": "object"}, handler=handler)
    )
    return reg


def test_loop_text_only_response_returns_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    conv = _FakeConversation([_result(text="hi")])
    monkeypatch.setattr(_anthropic, "Conversation", lambda **_: conv)
    result = run_agent_loop("hello", registry=ToolRegistry())
    assert result.text == "hi"
    assert len(conv.calls) == 1
    assert conv.calls[0]["prompt"] == "hello"


def test_loop_executes_tool_use_and_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    conv = _FakeConversation(
        [
            _result(tool_uses=[ToolUse(id="tu_1", name="echo", input={"text": "hi"})]),
            _result(text="final"),
        ]
    )
    monkeypatch.setattr(_anthropic, "Conversation", lambda **_: conv)
    captured: list[dict] = []
    reg = _registry(lambda **kwargs: captured.append(kwargs) or "echoed hi")
    result = run_agent_loop("hello", registry=reg)
    assert result.text == "final"
    assert captured == [{"text": "hi"}]
    assert len(conv.calls) == 2
    second = conv.calls[1]
    assert second.get("tool_results")
    assert second["tool_results"][0].output == "echoed hi"


def test_loop_respects_max_iterations(monkeypatch: pytest.MonkeyPatch) -> None:
    def looping_responses():
        return _result(tool_uses=[ToolUse(id="tu_x", name="echo", input={"text": "x"})])

    conv = _FakeConversation([looping_responses(), looping_responses(), looping_responses()])
    monkeypatch.setattr(_anthropic, "Conversation", lambda **_: conv)
    reg = _registry(lambda **_: "x")
    result = run_agent_loop("hi", registry=reg, max_iterations=2)
    # max_iterations=2 → initial send + 2 follow-ups = 3 total calls
    assert len(conv.calls) == 3
    assert result.tool_uses  # last response was still tool_use because cap hit


def test_loop_max_iterations_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_iterations"):
        run_agent_loop("hi", registry=ToolRegistry(), max_iterations=0)


def test_loop_handler_exception_becomes_tool_result_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conv = _FakeConversation(
        [
            _result(tool_uses=[ToolUse(id="tu_1", name="echo", input={})]),
            _result(text="recovered"),
        ]
    )
    monkeypatch.setattr(_anthropic, "Conversation", lambda **_: conv)

    def boom(**_):
        raise RuntimeError("explode")

    reg = _registry(boom)
    result = run_agent_loop("hi", registry=reg)
    assert result.text == "recovered"
    second = conv.calls[1]
    assert second["tool_results"][0].error == "RuntimeError: explode"


def test_loop_dispatches_to_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    conv = _FakeConversation([_result(text="hi from gemini")])
    monkeypatch.setattr(_gemini, "Conversation", lambda **_: conv)
    result = run_agent_loop("hi", registry=ToolRegistry(), provider="gemini")
    assert result.text == "hi from gemini"


def test_loop_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown provider"):
        run_agent_loop("hi", registry=ToolRegistry(), provider="openai")


def test_loop_on_tool_result_callback_fires(monkeypatch: pytest.MonkeyPatch) -> None:
    conv = _FakeConversation(
        [
            _result(tool_uses=[ToolUse(id="tu_1", name="echo", input={"text": "y"})]),
            _result(text="done"),
        ]
    )
    monkeypatch.setattr(_anthropic, "Conversation", lambda **_: conv)
    reg = _registry(lambda **kwargs: kwargs)
    logged: list = []
    run_agent_loop("hi", registry=reg, on_tool_result=logged.append)
    assert len(logged) == 1
    assert logged[0].name == "echo"
