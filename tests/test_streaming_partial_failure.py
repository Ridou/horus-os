"""Streaming partial-failure tests.

Phase 19 gap B: provider-level streaming tests cover the happy path
and the `ToolCallEvent` emission, but not what happens when the
provider stream raises mid-flight or the final assembled message has
defensive holes (empty content list, tool_use block missing the
expected `name` and `input` attributes).

The SSE server test covers an error raised before any yield. This
file covers the more realistic case: tokens have already been
streamed, then the provider raises. The error trace must persist with
the partial text.
"""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from typing import Any, ClassVar

import pytest
from fastapi.testclient import TestClient

from horus_os import Database, create_app
from horus_os._providers import _anthropic
from horus_os.server import api as server_api
from horus_os.types import ToolCallEvent

# ---------------------------------------------------------------------------
# Fake Anthropic streaming SDK with a configurable mid-flight error
# ---------------------------------------------------------------------------


class _Block:
    def __init__(self, **fields: Any) -> None:
        for key, value in fields.items():
            setattr(self, key, value)


class _Response:
    def __init__(self, content: list[Any]) -> None:
        self.content = content


class _FakeMessageStream:
    """A `text_stream` whose async generator can raise after N tokens."""

    def __init__(
        self,
        tokens: list[str],
        final_blocks: list[Any],
        raise_after: int | None = None,
        exc: BaseException | None = None,
    ) -> None:
        self._tokens = tokens
        self._final_blocks = final_blocks
        self._raise_after = raise_after
        self._exc = exc

    @property
    def text_stream(self) -> Any:
        async def _gen() -> Any:
            for i, token in enumerate(self._tokens):
                if self._raise_after is not None and i == self._raise_after:
                    assert self._exc is not None
                    raise self._exc
                yield token

        return _gen()

    async def get_final_message(self) -> _Response:
        return _Response(content=self._final_blocks)


class _FakeStreamContext:
    def __init__(self, stream: _FakeMessageStream) -> None:
        self._stream = stream

    async def __aenter__(self) -> _FakeMessageStream:
        return self._stream

    async def __aexit__(self, *_: Any) -> None:
        return None


class _FakeStreamingAnthropic:
    next_tokens: ClassVar[list[str]] = []
    next_final_blocks: ClassVar[list[Any]] = []
    raise_after: ClassVar[int | None] = None
    raise_exc: ClassVar[BaseException | None] = None

    def __init__(self, *_: Any, **__: Any) -> None:
        self.messages = self

    def stream(self, **_kwargs: Any) -> _FakeStreamContext:
        msg = _FakeMessageStream(
            tokens=list(_FakeStreamingAnthropic.next_tokens),
            final_blocks=list(_FakeStreamingAnthropic.next_final_blocks),
            raise_after=_FakeStreamingAnthropic.raise_after,
            exc=_FakeStreamingAnthropic.raise_exc,
        )
        return _FakeStreamContext(msg)


@pytest.fixture
def fake_streaming_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("anthropic")
    # _anthropic.Conversation.__init__ also imports Anthropic. Provide a
    # placeholder; the streaming path only uses AsyncAnthropic.
    module.Anthropic = object  # type: ignore[attr-defined]
    module.AsyncAnthropic = _FakeStreamingAnthropic  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "anthropic", module)
    _FakeStreamingAnthropic.next_tokens = []
    _FakeStreamingAnthropic.next_final_blocks = []
    _FakeStreamingAnthropic.raise_after = None
    _FakeStreamingAnthropic.raise_exc = None


async def _collect(gen: Any) -> list[Any]:
    return [item async for item in gen]


# ---------------------------------------------------------------------------
# Tests: provider-level partial failure
# ---------------------------------------------------------------------------


def test_stream_anthropic_async_propagates_midflight_exception(
    fake_streaming_anthropic: None,
) -> None:
    """If the provider raises after the first token, the partial text
    is still observed before the exception surfaces.

    Closes the gap that no prior test covers a stream that errors
    after some tokens already shipped.
    """
    _FakeStreamingAnthropic.next_tokens = ["Hello ", "world", "should-not-appear"]
    _FakeStreamingAnthropic.next_final_blocks = []
    _FakeStreamingAnthropic.raise_after = 2
    _FakeStreamingAnthropic.raise_exc = RuntimeError("provider hiccup")

    collected: list[Any] = []

    async def _drive() -> None:
        async for item in _anthropic.stream_anthropic_async("hi", model="claude-sonnet-4-6"):
            collected.append(item)

    with pytest.raises(RuntimeError, match="provider hiccup"):
        asyncio.run(_drive())
    # The first two tokens reached the caller before the raise.
    assert collected == ["Hello ", "world"]


def test_stream_anthropic_async_handles_empty_final_message(
    fake_streaming_anthropic: None,
) -> None:
    """A final message with an empty content list yields no
    ToolCallEvent and does not raise.

    This guards against an SDK contract change where `final_msg.content`
    could legitimately be empty (text-only completion with no blocks
    in the final assembled view).
    """
    _FakeStreamingAnthropic.next_tokens = ["ok"]
    _FakeStreamingAnthropic.next_final_blocks = []
    items = asyncio.run(_collect(_anthropic.stream_anthropic_async("hi", model="m")))
    assert items == ["ok"]
    # No tool events emitted from an empty content list.
    assert not any(isinstance(i, ToolCallEvent) for i in items)


def test_stream_anthropic_async_tolerates_malformed_tool_use_block(
    fake_streaming_anthropic: None,
) -> None:
    """A tool_use block missing `name` and `input` does not crash;
    the helper falls back to empty defaults.

    The provider helper uses `getattr(block, "name", "")` and
    `dict(getattr(block, "input", {}) or {})`. This test pins that
    defensive contract.
    """
    _FakeStreamingAnthropic.next_tokens = ["calling"]
    _FakeStreamingAnthropic.next_final_blocks = [
        _Block(type="text", text="calling"),
        _Block(type="tool_use"),  # no name, no input
    ]
    items = asyncio.run(_collect(_anthropic.stream_anthropic_async("hi", model="m")))
    assert items[0] == "calling"
    assert len(items) == 2
    event = items[1]
    assert isinstance(event, ToolCallEvent)
    assert event.name == ""
    assert event.input == {}


# ---------------------------------------------------------------------------
# SSE endpoint partial-text-then-error
# ---------------------------------------------------------------------------


def _init_db(tmp_path: Path) -> Database:
    from horus_os import Config

    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()
    return db


def test_sse_records_partial_text_when_stream_raises_midflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The SSE endpoint, when the provider yields tokens then raises,
    persists an error trace whose response_text holds the partial
    accumulator and whose status is error.

    Phase 16 covered a stream that raises before any yield. This is
    the realistic case: the user has seen some tokens paint, then
    the connection dies.
    """
    db = _init_db(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")

    async def fake_stream(prompt: str, **_: Any) -> Any:
        yield "Once upon "
        yield "a time"
        raise RuntimeError("upstream cut")

    monkeypatch.setattr(server_api, "run_agent_stream", fake_stream)
    client = TestClient(create_app(data_dir=tmp_path))
    response = client.post("/api/chat/stream", json={"prompt": "tell me a story"})
    assert response.status_code == 200
    # An error trace landed with the partial accumulator preserved.
    traces = db.list_traces()
    assert len(traces) == 1
    record = traces[0]
    assert record.status == "error"
    assert record.response_text == "Once upon a time"
    assert "upstream cut" in (record.error_message or "")
