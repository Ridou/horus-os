"""TEST-32: a full agent turn against a mocked local OpenAI-compatible endpoint.

Drives the real `run_agent_loop` with provider="local" while both cloud
keys (ANTHROPIC_API_KEY, GOOGLE_API_KEY / GEMINI_API_KEY) are removed from
the environment, proving PROJECT.md core value #1: a full agent turn runs
with zero cloud API key.

A fake `openai` module is injected into sys.modules so no real client is
constructed and no network call is made. The first scripted response
carries a tool_call; the second returns text. The test asserts the loop
returns the final text AND that the registered tool actually ran (LP-1
resolved: a tool_use, not a prose fallback), and that an LLMCallEvent was
published on the observation bus.
"""

from __future__ import annotations

import json
import sys
import types
from typing import Any, ClassVar

import pytest

from horus_os.agent import run_agent_loop
from horus_os.observability import (
    get_observation_bus,
    reset_observation_bus_for_tests,
)
from horus_os.observability.bus import LLMCallEvent, ObservationEvent
from horus_os.tools.registry import ToolRegistry
from horus_os.types import Tool


class _Function:
    def __init__(self, name: str, arguments: Any) -> None:
        self.name = name
        self.arguments = arguments


class _ToolCall:
    def __init__(self, id: str, name: str, arguments: Any) -> None:
        self.id = id
        self.type = "function"
        self.function = _Function(name, arguments)
        self.index = 0


class _Message:
    def __init__(self, content: str | None, tool_calls: list[_ToolCall] | None = None) -> None:
        self.content = content
        self.tool_calls = tool_calls


class _Choice:
    def __init__(self, message: _Message) -> None:
        self.message = message


class _Usage:
    def __init__(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class _Response:
    def __init__(self, choices: list[_Choice], usage: _Usage | None = None) -> None:
        self.choices = choices
        self.usage = usage


class _Completions:
    def __init__(self, scripted: list[_Response]) -> None:
        self._scripted = scripted

    def create(self, **kwargs: Any) -> _Response:
        if not self._scripted:
            raise AssertionError("fake openai ran out of scripted responses")
        return self._scripted.pop(0)


class _Chat:
    def __init__(self, scripted: list[_Response]) -> None:
        self.completions = _Completions(scripted)


class _FakeOpenAI:
    scripted: ClassVar[list[_Response]] = []

    def __init__(self, **kwargs: Any) -> None:
        self.chat = _Chat(_FakeOpenAI.scripted)


@pytest.fixture
def fake_openai_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    module = types.ModuleType("openai")
    module.OpenAI = _FakeOpenAI  # type: ignore[attr-defined]
    module.AsyncOpenAI = _FakeOpenAI  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openai", module)
    return module


@pytest.fixture(autouse=True)
def _fresh_bus() -> Any:
    reset_observation_bus_for_tests()
    yield
    reset_observation_bus_for_tests()


def _echo_registry(captured: list[dict]) -> ToolRegistry:
    reg = ToolRegistry()

    def _handler(**kwargs: Any) -> str:
        captured.append(kwargs)
        return f"echoed {kwargs.get('text', '')}"

    reg.register(
        Tool(name="echo", description="echo back", parameters={"type": "object"}, handler=_handler)
    )
    return reg


def test_full_local_agent_turn_runs_tool_without_cloud_key(
    fake_openai_module: types.ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No cloud key set: a full agent turn must still run on the local provider.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    # First response asks for the echo tool; second returns final text.
    _FakeOpenAI.scripted = [
        _Response(
            choices=[
                _Choice(
                    _Message(
                        content="",
                        tool_calls=[
                            _ToolCall(
                                id="call_1", name="echo", arguments=json.dumps({"text": "hi"})
                            )
                        ],
                    )
                )
            ],
            usage=_Usage(prompt_tokens=10, completion_tokens=4),
        ),
        _Response(
            choices=[_Choice(_Message(content="all done"))],
            usage=_Usage(prompt_tokens=12, completion_tokens=3),
        ),
    ]

    events: list[ObservationEvent] = []
    get_observation_bus().subscribe(events.append)

    captured: list[dict] = []
    registry = _echo_registry(captured)

    result = run_agent_loop("please echo hi", registry=registry, provider="local", model="llama3.2")

    # Final text from the second turn.
    assert result.text == "all done"
    assert result.provider == "local"
    # LP-1 resolved: the tool actually ran, not a prose fallback.
    assert captured == [{"text": "hi"}]
    # An LLMCallEvent was published with the local provider and usage.
    llm_events = [e for e in events if isinstance(e, LLMCallEvent)]
    assert llm_events, "expected at least one LLMCallEvent on the bus"
    assert all(e.provider == "local" for e in llm_events)
    assert any(e.input_tokens == 10 and e.output_tokens == 4 for e in llm_events)
    assert all(e.status == "success" for e in llm_events)
