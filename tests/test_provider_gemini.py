"""Google Gemini provider tests.

Replace the `google.genai` SDK module in sys.modules with a fake so no
real client is ever constructed and no API key is required.
"""

from __future__ import annotations

import asyncio
import sys
import types
from typing import Any

import pytest

from horus_os._providers import _gemini
from horus_os.types import Tool


class _Part:
    def __init__(self, **fields: Any) -> None:
        for key, value in fields.items():
            setattr(self, key, value)


class _Content:
    def __init__(self, parts: list[_Part]) -> None:
        self.parts = parts


class _Candidate:
    def __init__(self, content: _Content) -> None:
        self.content = content


class _UsageMetadata:
    def __init__(self, prompt: int, candidates: int, total: int) -> None:
        self.prompt_token_count = prompt
        self.candidates_token_count = candidates
        self.total_token_count = total


class _Response:
    def __init__(
        self,
        candidates: list[_Candidate],
        usage_metadata: _UsageMetadata | None = None,
    ) -> None:
        self.candidates = candidates
        self.usage_metadata = usage_metadata


class _FakeModels:
    last_request: dict[str, Any] | None = None
    next_response: _Response | None = None

    def generate_content(self, **kwargs: Any) -> _Response:
        _FakeModels.last_request = kwargs
        return _FakeModels.next_response  # type: ignore[return-value]


class _FakeAsyncModels:
    last_request: dict[str, Any] | None = None
    next_response: _Response | None = None

    async def generate_content(self, **kwargs: Any) -> _Response:
        _FakeAsyncModels.last_request = kwargs
        return _FakeAsyncModels.next_response  # type: ignore[return-value]


class _FakeAioNamespace:
    def __init__(self) -> None:
        self.models = _FakeAsyncModels()


class _FakeClient:
    last_init_kwargs: dict[str, Any] | None = None

    def __init__(self, **kwargs: Any) -> None:
        _FakeClient.last_init_kwargs = kwargs
        self.models = _FakeModels()
        self.aio = _FakeAioNamespace()


class _FakeTool:
    def __init__(self, function_declarations: list[Any]) -> None:
        self.function_declarations = function_declarations


class _FakeGenerateContentConfig:
    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture
def fake_gemini_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    """Install a fake `google.genai` module hierarchy."""
    google_module = types.ModuleType("google")
    genai_module = types.ModuleType("google.genai")
    types_module = types.ModuleType("google.genai.types")
    types_module.Tool = _FakeTool  # type: ignore[attr-defined]
    types_module.GenerateContentConfig = _FakeGenerateContentConfig  # type: ignore[attr-defined]
    genai_module.Client = _FakeClient  # type: ignore[attr-defined]
    genai_module.types = types_module  # type: ignore[attr-defined]
    google_module.genai = genai_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.genai", genai_module)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_module)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    _FakeModels.last_request = None
    _FakeModels.next_response = None
    _FakeAsyncModels.last_request = None
    _FakeAsyncModels.next_response = None
    _FakeClient.last_init_kwargs = None
    return genai_module


def test_text_response_returns_agent_result(fake_gemini_module: types.ModuleType) -> None:
    _FakeModels.next_response = _Response(
        candidates=[_Candidate(content=_Content(parts=[_Part(text="hello")]))],
        usage_metadata=_UsageMetadata(prompt=3, candidates=1, total=4),
    )
    result = _gemini.call_gemini("hi")
    assert result.provider == "gemini"
    assert result.model == "gemini-2.5-flash"
    assert result.text == "hello"
    assert result.tool_uses == []
    assert result.usage == {
        "prompt_token_count": 3,
        "candidates_token_count": 1,
        "total_token_count": 4,
    }


def test_function_call_is_captured(fake_gemini_module: types.ModuleType) -> None:
    function_call = _Part(
        function_call=_Part(id="fc_1", name="echo", args={"text": "hi"}),
    )
    _FakeModels.next_response = _Response(
        candidates=[_Candidate(content=_Content(parts=[function_call]))],
    )
    tool = Tool(name="echo", description="echo back", parameters={"type": "object"})
    result = _gemini.call_gemini("say hi", tools=[tool])
    assert len(result.tool_uses) == 1
    use = result.tool_uses[0]
    assert use.name == "echo"
    assert use.input == {"text": "hi"}
    request = _FakeModels.last_request
    assert request is not None
    config = request["config"]
    assert hasattr(config, "tools")
    assert config.tools[0].function_declarations[0] == {
        "name": "echo",
        "description": "echo back",
        "parameters": {"type": "object"},
    }


def test_gemini_api_key_is_read_first(
    fake_gemini_module: types.ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-secret")
    _FakeModels.next_response = _Response(
        candidates=[_Candidate(content=_Content(parts=[_Part(text="ok")]))]
    )
    _gemini.call_gemini("hi")
    assert _FakeClient.last_init_kwargs == {"api_key": "gemini-secret"}


def test_google_api_key_is_fallback(
    fake_gemini_module: types.ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "google-secret")
    _FakeModels.next_response = _Response(
        candidates=[_Candidate(content=_Content(parts=[_Part(text="ok")]))]
    )
    _gemini.call_gemini("hi")
    assert _FakeClient.last_init_kwargs == {"api_key": "google-secret"}


def test_async_call_returns_agent_result(fake_gemini_module: types.ModuleType) -> None:
    _FakeAsyncModels.next_response = _Response(
        candidates=[_Candidate(content=_Content(parts=[_Part(text="hi back")]))],
        usage_metadata=_UsageMetadata(prompt=1, candidates=2, total=3),
    )
    result = asyncio.run(_gemini.call_gemini_async("hi"))
    assert result.text == "hi back"
    assert result.usage == {
        "prompt_token_count": 1,
        "candidates_token_count": 2,
        "total_token_count": 3,
    }
