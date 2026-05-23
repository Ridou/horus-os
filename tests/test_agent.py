"""Tests for the top-level agent dispatcher.

Both provider modules are stubbed at the dispatcher boundary so these
tests never reach a real SDK or network.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from horus_os import (
    AgentResult,
    Tool,
    ToolCallEvent,
    run_agent,
    run_agent_async,
    run_agent_stream,
)
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


async def _collect(gen: Any) -> list[Any]:
    return [item async for item in gen]


def test_run_agent_stream_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_stream(prompt: str, **kwargs: Any) -> Any:
        for token in ["hello", " world"]:
            yield token

    monkeypatch.setattr(_anthropic, "stream_anthropic_async", fake_stream)
    items = asyncio.run(_collect(run_agent_stream("hi", provider="anthropic")))
    assert items == ["hello", " world"]


def test_run_agent_stream_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_stream(prompt: str, **kwargs: Any) -> Any:
        for token in ["hola", " mundo"]:
            yield token

    monkeypatch.setattr(_gemini, "stream_gemini_async", fake_stream)
    items = asyncio.run(_collect(run_agent_stream("hi", provider="gemini")))
    assert items == ["hola", " mundo"]


def test_run_agent_stream_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown provider"):
        asyncio.run(_collect(run_agent_stream("hi", provider="openai")))


def test_run_agent_stream_passes_model_and_system(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_stream(prompt: str, **kwargs: Any) -> Any:
        captured["prompt"] = prompt
        captured.update(kwargs)
        yield "ok"

    monkeypatch.setattr(_anthropic, "stream_anthropic_async", fake_stream)
    asyncio.run(
        _collect(
            run_agent_stream(
                "hi",
                provider="anthropic",
                model="claude-haiku-4-5",
                max_tokens=512,
                system="you are helpful",
            )
        )
    )
    assert captured["prompt"] == "hi"
    assert captured["model"] == "claude-haiku-4-5"
    assert captured["max_tokens"] == 512
    assert captured["system"] == "you are helpful"


def test_run_agent_stream_default_model_falls_back_to_provider_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_anthropic: dict[str, Any] = {}
    captured_gemini: dict[str, Any] = {}

    async def fake_anthropic_stream(prompt: str, **kwargs: Any) -> Any:
        captured_anthropic.update(kwargs)
        yield "ok"

    async def fake_gemini_stream(prompt: str, **kwargs: Any) -> Any:
        captured_gemini.update(kwargs)
        yield "ok"

    monkeypatch.setattr(_anthropic, "stream_anthropic_async", fake_anthropic_stream)
    monkeypatch.setattr(_gemini, "stream_gemini_async", fake_gemini_stream)
    asyncio.run(_collect(run_agent_stream("hi", provider="anthropic")))
    asyncio.run(_collect(run_agent_stream("hi", provider="gemini")))
    assert captured_anthropic["model"] == _anthropic.DEFAULT_MODEL
    assert captured_gemini["model"] == _gemini.DEFAULT_MODEL


def test_run_agent_stream_forwards_tool_call_events(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_stream(prompt: str, **kwargs: Any) -> Any:
        yield "calling"
        yield ToolCallEvent(name="echo", input={"text": "hi"})

    monkeypatch.setattr(_anthropic, "stream_anthropic_async", fake_stream)
    items = asyncio.run(_collect(run_agent_stream("hi", provider="anthropic")))
    assert items[0] == "calling"
    assert isinstance(items[1], ToolCallEvent)
    assert items[1].name == "echo"
    assert items[1].input == {"text": "hi"}


def test_run_agent_stream_and_tool_call_event_are_public() -> None:
    """Smoke test: package-level imports for the Phase 14 surface."""
    from horus_os import ToolCallEvent as PublicToolCallEvent
    from horus_os import run_agent_stream as public_run_agent_stream

    assert public_run_agent_stream is run_agent_stream
    assert PublicToolCallEvent is ToolCallEvent
