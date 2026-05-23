"""Tests for the Gemini Conversation class."""

from __future__ import annotations

import sys
import types
from typing import Any, ClassVar

import pytest

from horus_os._providers import _gemini
from horus_os.types import Tool, ToolResult


class _Part:
    def __init__(self, **fields: Any) -> None:
        for key, value in fields.items():
            setattr(self, key, value)


class _Content:
    def __init__(self, role: str, parts: list[_Part]) -> None:
        self.role = role
        self.parts = parts


class _Candidate:
    def __init__(self, content: _Content) -> None:
        self.content = content


class _Response:
    def __init__(self, candidates: list[_Candidate]) -> None:
        self.candidates = candidates
        self.usage_metadata = None


class _FakeModels:
    requests: ClassVar[list[dict[str, Any]]] = []
    responses: ClassVar[list[_Response]] = []

    def generate_content(self, **kwargs: Any) -> _Response:
        _FakeModels.requests.append(kwargs)
        if not _FakeModels.responses:
            raise RuntimeError("no scripted response left")
        return _FakeModels.responses.pop(0)


class _FakeAio:
    def __init__(self) -> None:
        self.models = _FakeModels()


class _FakeClient:
    def __init__(self, **_: Any) -> None:
        self.models = _FakeModels()
        self.aio = _FakeAio()


class _FakeFunctionResponse:
    def __init__(self, *, name: str, response: dict) -> None:
        self.name = name
        self.response = response


class _FakeTool:
    def __init__(self, function_declarations: list[Any]) -> None:
        self.function_declarations = function_declarations


class _FakeConfig:
    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture
def fake_gemini(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    google_module = types.ModuleType("google")
    genai_module = types.ModuleType("google.genai")
    types_module = types.ModuleType("google.genai.types")
    types_module.Content = _Content  # type: ignore[attr-defined]
    types_module.Part = _Part  # type: ignore[attr-defined]
    types_module.FunctionResponse = _FakeFunctionResponse  # type: ignore[attr-defined]
    types_module.Tool = _FakeTool  # type: ignore[attr-defined]
    types_module.GenerateContentConfig = _FakeConfig  # type: ignore[attr-defined]
    genai_module.Client = _FakeClient  # type: ignore[attr-defined]
    genai_module.types = types_module  # type: ignore[attr-defined]
    google_module.genai = genai_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.genai", genai_module)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_module)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    _FakeModels.requests = []
    _FakeModels.responses = []
    return genai_module


def test_conversation_initial_prompt(fake_gemini) -> None:
    _FakeModels.responses = [_Response([_Candidate(_Content("model", [_Part(text="hi")]))])]
    result = _gemini.Conversation().send(prompt="hello")
    assert result.text == "hi"
    request = _FakeModels.requests[0]
    contents = request["contents"]
    assert len(contents) == 1
    assert contents[0].role == "user"
    assert contents[0].parts[0].text == "hello"


def test_conversation_function_call_then_results(fake_gemini) -> None:
    call_part = _Part(function_call=_Part(id="fc_1", name="echo", args={"text": "hi"}))
    model_content = _Content("model", [call_part])
    _FakeModels.responses = [
        _Response([_Candidate(model_content)]),
        _Response([_Candidate(_Content("model", [_Part(text="done")]))]),
    ]
    conv = _gemini.Conversation()
    tool = Tool(name="echo", description="echo", parameters={"type": "object"})
    first = conv.send(prompt="say hi", tools=[tool])
    assert first.tool_uses[0].name == "echo"

    result = ToolResult(tool_use_id="fc_1", name="echo", output="hi")
    second = conv.send(tool_results=[result], tools=[tool])
    assert second.text == "done"

    second_request = _FakeModels.requests[1]
    contents = second_request["contents"]
    # contents: [user prompt, model response, user tool_response]
    assert contents[1] is model_content
    assert contents[2].role == "user"
    fr = contents[2].parts[0].function_response
    assert fr.name == "echo"
    assert fr.response == {"content": "hi"}


def test_conversation_function_error_payload(fake_gemini) -> None:
    call_part = _Part(function_call=_Part(id="fc_1", name="echo", args={}))
    _FakeModels.responses = [
        _Response([_Candidate(_Content("model", [call_part]))]),
        _Response([_Candidate(_Content("model", [_Part(text="ok")]))]),
    ]
    conv = _gemini.Conversation()
    conv.send(prompt="hi")
    conv.send(tool_results=[ToolResult(tool_use_id="fc_1", name="echo", error="boom")])
    second_request = _FakeModels.requests[1]
    fr = second_request["contents"][2].parts[0].function_response
    assert fr.response == {"error": "boom"}


def test_conversation_send_requires_argument(fake_gemini) -> None:
    conv = _gemini.Conversation()
    with pytest.raises(ValueError, match="requires either prompt or tool_results"):
        conv.send()


def test_conversation_send_rejects_both(fake_gemini) -> None:
    conv = _gemini.Conversation()
    with pytest.raises(ValueError, match="accepts prompt or tool_results"):
        conv.send(prompt="hi", tool_results=[])


def test_conversation_passes_tools_through_config(fake_gemini) -> None:
    _FakeModels.responses = [_Response([_Candidate(_Content("model", [_Part(text="ok")]))])]
    tool = Tool(name="echo", description="d", parameters={"type": "object"})
    _gemini.Conversation().send(prompt="hi", tools=[tool])
    request = _FakeModels.requests[0]
    config = request["config"]
    assert hasattr(config, "tools")
    fn_decls = config.tools[0].function_declarations
    assert fn_decls == [{"name": "echo", "description": "d", "parameters": {"type": "object"}}]
