"""Tests for the top-level agent dispatcher.

Both provider modules are stubbed at the dispatcher boundary so these
tests never reach a real SDK or network.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from horus_os import AgentResult, Tool, run_agent, run_agent_async
from horus_os._providers import _anthropic, _gemini


def _fake_result(provider: str, model: str = "test-model") -> AgentResult:
    return AgentResult(text="ok", tool_uses=[], provider=provider, model=model, usage={})


def test_run_agent_dispatches_to_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_call(prompt: str, **kwargs: Any) -> AgentResult:
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
        return _fake_result("anthropic", "claude-sonnet-4-6")

    monkeypatch.setattr(_anthropic, "call_anthropic", fake_call)
    result = run_agent("hello", provider="anthropic")
    assert result.provider == "anthropic"
    assert captured["prompt"] == "hello"


def test_run_agent_dispatches_to_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_call(prompt: str, **kwargs: Any) -> AgentResult:
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
        return _fake_result("gemini", "gemini-2.5-flash")

    monkeypatch.setattr(_gemini, "call_gemini", fake_call)
    result = run_agent("hello", provider="gemini")
    assert result.provider == "gemini"
    assert captured["prompt"] == "hello"


def test_run_agent_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown provider"):
        run_agent("hello", provider="openai")


def test_run_agent_passes_tools_and_model(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    tool = Tool(name="echo", description="echo back", parameters={"type": "object"})

    def fake_call(prompt: str, **kwargs: Any) -> AgentResult:
        captured.update(kwargs)
        return _fake_result("anthropic")

    monkeypatch.setattr(_anthropic, "call_anthropic", fake_call)
    run_agent("hi", provider="anthropic", tools=[tool], model="claude-haiku-4-5")
    assert captured["tools"] == [tool]
    assert captured["model"] == "claude-haiku-4-5"


def test_run_agent_async_dispatches_to_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call(prompt: str, **kwargs: Any) -> AgentResult:
        return _fake_result("anthropic")

    monkeypatch.setattr(_anthropic, "call_anthropic_async", fake_call)
    result = asyncio.run(run_agent_async("hi", provider="anthropic"))
    assert result.provider == "anthropic"


def test_run_agent_async_dispatches_to_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call(prompt: str, **kwargs: Any) -> AgentResult:
        return _fake_result("gemini")

    monkeypatch.setattr(_gemini, "call_gemini_async", fake_call)
    result = asyncio.run(run_agent_async("hi", provider="gemini"))
    assert result.provider == "gemini"


def test_run_agent_async_rejects_unknown_provider() -> None:
    async def _runner() -> None:
        await run_agent_async("hi", provider="openai")

    with pytest.raises(ValueError, match="Unknown provider"):
        asyncio.run(_runner())
