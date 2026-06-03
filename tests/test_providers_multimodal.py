"""Tests for multimodal user-message construction in both providers.

These assert the message SHAPE built by Conversation.send when a `content`
list of provider-neutral blocks is passed: Anthropic builds a base64 image
block plus a text block; Gemini builds a Content with a text Part and an
inline-data Part. The plain-string prompt path must stay byte-identical, so
each provider also has a string-path regression here. No network call is made:
the SDK client is stubbed to capture the request and return a canned response.
"""

from __future__ import annotations

import base64
from typing import Any, ClassVar

import pytest

# These exercise the real provider SDKs ([anthropic] and [gemini] extras).
# Skip when absent (the bare [dev] CI install); the [all] install-smoke
# variant installs both SDKs.
pytest.importorskip("anthropic")
pytest.importorskip("google.genai")

from horus_os._providers import _anthropic, _gemini


class _FakeAnthropicResponse:
    def __init__(self) -> None:
        self.content: list[Any] = []
        self.usage = None


class _FakeAnthropicMessages:
    def __init__(self) -> None:
        self.captured: dict[str, Any] | None = None

    def create(self, **request: Any) -> _FakeAnthropicResponse:
        self.captured = request
        return _FakeAnthropicResponse()


class _FakeAnthropicClient:
    def __init__(self) -> None:
        self.messages = _FakeAnthropicMessages()


def _anthropic_conversation(monkeypatch: pytest.MonkeyPatch) -> Any:
    import anthropic

    fake = _FakeAnthropicClient()
    # Conversation.__init__ does `from anthropic import Anthropic`, so patch the
    # SDK module attribute the import binds to. No network client is built.
    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: fake)
    conv = _anthropic.Conversation(model="claude-sonnet-4-6")
    return conv, fake


def test_anthropic_content_builds_image_and_text_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conv, fake = _anthropic_conversation(monkeypatch)
    data_b64 = base64.b64encode(b"PNGDATA").decode("ascii")
    conv.send(
        content=[
            {"type": "text", "text": "what is this"},
            {"type": "image", "media_type": "image/png", "data_b64": data_b64},
        ]
    )
    message = fake.messages.captured["messages"][-1]
    assert message["role"] == "user"
    blocks = message["content"]
    assert isinstance(blocks, list)
    text_blocks = [b for b in blocks if b["type"] == "text"]
    image_blocks = [b for b in blocks if b["type"] == "image"]
    assert text_blocks[0]["text"] == "what is this"
    assert len(image_blocks) == 1
    source = image_blocks[0]["source"]
    assert source["type"] == "base64"
    assert source["media_type"] == "image/png"
    assert source["data"] == data_b64


def test_anthropic_string_prompt_path_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conv, fake = _anthropic_conversation(monkeypatch)
    conv.send(prompt="hello world")
    message = fake.messages.captured["messages"][-1]
    # Byte-identical string path: content is the plain string, not a block list.
    assert message == {"role": "user", "content": "hello world"}


def test_anthropic_send_rejects_multiple_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conv, _ = _anthropic_conversation(monkeypatch)
    with pytest.raises(ValueError, match="not more than one"):
        conv.send(prompt="hi", content=[{"type": "text", "text": "x"}])


# --- Gemini ---------------------------------------------------------------


class _FakeGeminiResponse:
    candidates: ClassVar[list[Any]] = []
    usage_metadata = None


class _FakeGeminiModels:
    def __init__(self) -> None:
        self.captured: dict[str, Any] | None = None

    def generate_content(self, **request: Any) -> _FakeGeminiResponse:
        self.captured = request
        return _FakeGeminiResponse()


class _FakeGeminiClient:
    def __init__(self, *a: Any, **k: Any) -> None:
        self.models = _FakeGeminiModels()


def _gemini_conversation(monkeypatch: pytest.MonkeyPatch) -> Any:
    from google import genai

    fake = _FakeGeminiClient()
    monkeypatch.setattr(genai, "Client", lambda *a, **k: fake)
    conv = _gemini.Conversation(model="gemini-2.5-flash")
    return conv, fake


def test_gemini_content_builds_text_and_inline_data_parts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conv, fake = _gemini_conversation(monkeypatch)
    raw = b"PNGDATA"
    data_b64 = base64.b64encode(raw).decode("ascii")
    conv.send(
        content=[
            {"type": "text", "text": "what is this"},
            {"type": "image", "media_type": "image/png", "data_b64": data_b64},
        ]
    )
    contents = fake.models.captured["contents"]
    last = contents[-1]
    assert last.role == "user"
    parts = last.parts
    text_parts = [p for p in parts if getattr(p, "text", None)]
    inline_parts = [p for p in parts if getattr(p, "inline_data", None) is not None]
    assert text_parts[0].text == "what is this"
    assert len(inline_parts) == 1
    inline = inline_parts[0].inline_data
    assert inline.mime_type == "image/png"
    assert inline.data == raw


def test_gemini_string_prompt_path_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conv, fake = _gemini_conversation(monkeypatch)
    conv.send(prompt="hello world")
    contents = fake.models.captured["contents"]
    last = contents[-1]
    assert last.role == "user"
    assert [p.text for p in last.parts] == ["hello world"]


def test_gemini_send_rejects_multiple_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conv, _ = _gemini_conversation(monkeypatch)
    with pytest.raises(ValueError, match="not more than one"):
        conv.send(prompt="hi", content=[{"type": "text", "text": "x"}])
