"""OpenAI-compatible local provider tests.

Inject a fake `openai` module into sys.modules so no real client is ever
constructed, no network call is made, and no cloud key is required. The
fakes return canned chat-completion objects shaped like the real SDK
(choices[0].message.content / message.tool_calls / usage).
"""

from __future__ import annotations

import asyncio
import json
import sys
import types
from typing import Any

import pytest

from horus_os._providers import _openai_compat
from horus_os.types import Tool, ToolResult


class _Function:
    def __init__(self, name: str, arguments: Any) -> None:
        self.name = name
        self.arguments = arguments


class _ToolCall:
    def __init__(self, id: str, name: str, arguments: Any, index: int = 0) -> None:
        self.id = id
        self.type = "function"
        self.function = _Function(name, arguments)
        self.index = index


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
    def __init__(self, owner: type[_FakeOpenAI] | type[_FakeAsyncOpenAI]) -> None:
        self._owner = owner

    def create(self, **kwargs: Any) -> _Response:
        self._owner.last_request = kwargs
        return self._owner.next_response  # type: ignore[return-value]


class _AsyncCompletions:
    def __init__(self, owner: type[_FakeAsyncOpenAI]) -> None:
        self._owner = owner

    async def create(self, **kwargs: Any) -> _Response:
        self._owner.last_request = kwargs
        return self._owner.next_response  # type: ignore[return-value]


class _Chat:
    def __init__(self, completions: Any) -> None:
        self.completions = completions


class _FakeOpenAI:
    last_request: dict[str, Any] | None = None
    next_response: _Response | None = None
    last_init: dict[str, Any] | None = None

    def __init__(self, **kwargs: Any) -> None:
        _FakeOpenAI.last_init = kwargs
        self.chat = _Chat(_Completions(_FakeOpenAI))


class _FakeAsyncOpenAI:
    last_request: dict[str, Any] | None = None
    next_response: _Response | None = None
    last_init: dict[str, Any] | None = None

    def __init__(self, **kwargs: Any) -> None:
        _FakeAsyncOpenAI.last_init = kwargs
        self.chat = _Chat(_AsyncCompletions(_FakeAsyncOpenAI))


@pytest.fixture
def fake_openai_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    """Install a fake `openai` module into sys.modules for the duration of a test."""
    module = types.ModuleType("openai")
    module.OpenAI = _FakeOpenAI  # type: ignore[attr-defined]
    module.AsyncOpenAI = _FakeAsyncOpenAI  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openai", module)
    _FakeOpenAI.last_request = None
    _FakeOpenAI.next_response = None
    _FakeOpenAI.last_init = None
    _FakeAsyncOpenAI.last_request = None
    _FakeAsyncOpenAI.next_response = None
    _FakeAsyncOpenAI.last_init = None
    return module


def test_text_response_returns_agent_result(fake_openai_module: types.ModuleType) -> None:
    _FakeOpenAI.next_response = _Response(
        choices=[_Choice(_Message(content="hello world"))],
        usage=_Usage(prompt_tokens=3, completion_tokens=2),
    )
    result = _openai_compat.call_openai_compat("hi", model="llama3.2")
    assert result.provider == "local"
    assert result.model == "llama3.2"
    assert result.text == "hello world"
    assert result.tool_uses == []
    assert result.usage == {"input_tokens": 3, "output_tokens": 2}


def test_tool_call_response_is_captured(fake_openai_module: types.ModuleType) -> None:
    _FakeOpenAI.next_response = _Response(
        choices=[
            _Choice(
                _Message(
                    content="",
                    tool_calls=[
                        _ToolCall(id="call_1", name="echo", arguments=json.dumps({"text": "hi"}))
                    ],
                )
            )
        ],
    )
    tool = Tool(name="echo", description="echo back", parameters={"type": "object"})
    result = _openai_compat.call_openai_compat("say hi", tools=[tool], model="llama3.2")
    assert len(result.tool_uses) == 1
    use = result.tool_uses[0]
    assert use.id == "call_1"
    assert use.name == "echo"
    assert use.input == {"text": "hi"}
    request = _FakeOpenAI.last_request
    assert request is not None
    assert request["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "echo",
                "description": "echo back",
                "parameters": {"type": "object"},
            },
        }
    ]
    # LP-1: a tool-using request must NOT enable streaming, or tool_calls
    # would be silently dropped by the OpenAI-compat endpoint.
    assert request.get("stream") in (None, False)


def test_tool_call_arguments_already_dict_not_double_parsed(
    fake_openai_module: types.ModuleType,
) -> None:
    _FakeOpenAI.next_response = _Response(
        choices=[
            _Choice(
                _Message(
                    content=None,
                    tool_calls=[_ToolCall(id="call_2", name="echo", arguments={"text": "raw"})],
                )
            )
        ],
    )
    result = _openai_compat.call_openai_compat("hi", model="llama3.2")
    assert result.tool_uses[0].input == {"text": "raw"}


def test_default_model_can_be_overridden(fake_openai_module: types.ModuleType) -> None:
    _FakeOpenAI.next_response = _Response(choices=[_Choice(_Message(content="ok"))])
    result = _openai_compat.call_openai_compat("hi", model="qwen2.5")
    assert result.model == "qwen2.5"
    request = _FakeOpenAI.last_request
    assert request is not None
    assert request["model"] == "qwen2.5"


def test_client_uses_loopback_base_url_and_placeholder_key(
    fake_openai_module: types.ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HORUS_OS_LOCAL_BASE_URL", raising=False)
    monkeypatch.delenv("HORUS_OS_LOCAL_API_KEY", raising=False)
    _FakeOpenAI.next_response = _Response(choices=[_Choice(_Message(content="ok"))])
    _openai_compat.call_openai_compat("hi", model="llama3.2")
    init = _FakeOpenAI.last_init
    assert init is not None
    assert init["base_url"] == "http://localhost:11434/v1"
    assert "0.0.0.0" not in init["base_url"]
    assert init["api_key"] == "horus-local"


def test_env_overrides_base_url_and_key(
    fake_openai_module: types.ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HORUS_OS_LOCAL_BASE_URL", "http://127.0.0.1:8080/v1")
    monkeypatch.setenv("HORUS_OS_LOCAL_API_KEY", "secret-key")
    _FakeOpenAI.next_response = _Response(choices=[_Choice(_Message(content="ok"))])
    _openai_compat.call_openai_compat("hi", model="llama3.2")
    init = _FakeOpenAI.last_init
    assert init is not None
    assert init["base_url"] == "http://127.0.0.1:8080/v1"
    assert init["api_key"] == "secret-key"


def test_async_call_returns_agent_result(fake_openai_module: types.ModuleType) -> None:
    _FakeAsyncOpenAI.next_response = _Response(
        choices=[_Choice(_Message(content="hi back"))],
        usage=_Usage(prompt_tokens=1, completion_tokens=2),
    )
    result = asyncio.run(_openai_compat.call_openai_compat_async("hi", model="llama3.2"))
    assert result.text == "hi back"
    assert result.usage == {"input_tokens": 1, "output_tokens": 2}


def test_conversation_threads_tool_results(fake_openai_module: types.ModuleType) -> None:
    conv = _openai_compat.Conversation(model="llama3.2", system_prompt="be terse")
    # First turn: model asks for a tool.
    _FakeOpenAI.next_response = _Response(
        choices=[
            _Choice(
                _Message(
                    content="",
                    tool_calls=[
                        _ToolCall(id="call_9", name="echo", arguments=json.dumps({"text": "hi"}))
                    ],
                )
            )
        ],
    )
    tool = Tool(name="echo", description="echo", parameters={"type": "object"})
    first = conv.send(prompt="say hi", tools=[tool])
    assert first.tool_uses[0].id == "call_9"
    # Second turn: feed the tool result back.
    _FakeOpenAI.next_response = _Response(choices=[_Choice(_Message(content="done"))])
    second = conv.send(
        tool_results=[ToolResult(tool_use_id="call_9", name="echo", output="echoed hi")],
        tools=[tool],
    )
    assert second.text == "done"
    messages = _FakeOpenAI.last_request["messages"]
    # The system message threads first, the assistant tool_calls message,
    # then the tool result keyed by tool_call_id.
    assert messages[0] == {"role": "system", "content": "be terse"}
    assistant = next(m for m in messages if m["role"] == "assistant")
    assert assistant["tool_calls"][0]["id"] == "call_9"
    tool_msg = next(m for m in messages if m["role"] == "tool")
    assert tool_msg["tool_call_id"] == "call_9"
    assert tool_msg["content"] == "echoed hi"
