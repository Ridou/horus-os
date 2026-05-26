"""Phase 33 Task 5 tests: SSE branch terminal-usage extraction (Pitfall 2).

The SSE handler in /api/chat/stream must read terminal usage from the
provider's `_StreamUsage` sentinel and persist non-zero token counts.
When the provider does not surface usage on a non-empty stream, the
handler falls back to a 4-char-per-token estimate. The canonical
warning-sign check is: no llm_calls row from a non-empty stream may
have input_tokens=0 AND output_tokens=0.
"""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest

from horus_os import Database
from horus_os._providers import _anthropic, _gemini
from horus_os._providers._stream_types import _StreamUsage
from horus_os.observability import reset_observation_bus_for_tests


def _stub_stream_anthropic(
    usage: dict, texts: list[str] | None = None, raise_after: int | None = None
):
    """Build an async generator that mimics stream_anthropic_async.

    `raise_after` raises ConnectionError after yielding that many texts
    (and before yielding the terminal _StreamUsage sentinel), so the
    SSE handler hits its exception path with partial text accumulated.
    """
    texts = texts or ["hello", " ", "world"]

    async def gen(*_args, **_kwargs) -> AsyncGenerator[object, None]:
        emitted = 0
        for t in texts:
            yield t
            emitted += 1
            if raise_after is not None and emitted >= raise_after:
                raise ConnectionError("stream aborted")
        # Only emit the terminal sentinel on the clean completion path.
        yield _StreamUsage(usage=usage)

    return gen


def _stub_stream_gemini(usage: dict, texts: list[str] | None = None):
    texts = texts or ["foo", " ", "bar"]

    async def gen(*_args, **_kwargs) -> AsyncGenerator[object, None]:
        for t in texts:
            yield t
        yield _StreamUsage(usage=usage)

    return gen


def _setup(tmp_path: Path, monkeypatch):
    from horus_os import create_app

    db = Database(tmp_path / "horus.sqlite")
    db.init()
    reset_observation_bus_for_tests()
    # Fake API key so the chat-stream handler does not 503.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-used")
    app = create_app(data_dir=tmp_path)
    return db, app


def _trace_id_from_sse(body: str) -> str:
    """Extract trace_id from the SSE done frame in the response body."""
    import json

    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        payload = json.loads(line[len("data: ") :])
        if payload.get("type") in ("done", "error"):
            return payload["trace_id"]
    raise AssertionError(f"no done/error frame found in SSE body: {body!r}")


def test_sse_anthropic_usage_persisted(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    db, app = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        _anthropic,
        "stream_anthropic_async",
        _stub_stream_anthropic(
            usage={
                "input_tokens": 250,
                "output_tokens": 120,
                "cache_read_input_tokens": 30,
                "cache_creation_input_tokens": 10,
            }
        ),
    )
    with TestClient(app) as client:
        resp = client.post("/api/chat/stream", json={"prompt": "hi", "provider": "anthropic"})
    assert resp.status_code == 200, resp.text
    trace_id = _trace_id_from_sse(resp.text)
    with sqlite3.connect(str(db.path)) as conn:
        row = conn.execute(
            "SELECT input_tokens, output_tokens, cache_read_input_tokens, "
            "cache_creation_input_tokens, latency_ms FROM llm_calls WHERE trace_id = ?",
            (trace_id,),
        ).fetchone()
        rollup = conn.execute(
            "SELECT total_input_tokens, total_cost_usd FROM traces WHERE trace_id = ?",
            (trace_id,),
        ).fetchone()
    assert row is not None
    assert row[0] == 250
    assert row[1] == 120
    assert row[2] == 30
    assert row[3] == 10
    assert row[4] >= 0
    assert rollup is not None
    assert rollup[0] == 250
    # Phase 34: CostAnnotator now populates cost_usd for the bundled
    # claude-sonnet-4-6 rates. 250*3 + 120*15 + 30*0.30 + 10*3.75 = 2596.5
    # / 1_000_000 -> 0.0025965 -> round(6dp, banker's) -> 0.002596.
    assert rollup[1] == pytest.approx(0.002596, abs=1e-9)


def test_sse_gemini_usage_normalized(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    db, app = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        _gemini,
        "stream_gemini_async",
        _stub_stream_gemini(usage={"prompt_token_count": 400, "candidates_token_count": 150}),
    )
    with TestClient(app) as client:
        resp = client.post("/api/chat/stream", json={"prompt": "hi", "provider": "gemini"})
    assert resp.status_code == 200, resp.text
    trace_id = _trace_id_from_sse(resp.text)
    with sqlite3.connect(str(db.path)) as conn:
        row = conn.execute(
            "SELECT input_tokens, output_tokens, cache_read_input_tokens, "
            "cache_creation_input_tokens FROM llm_calls WHERE trace_id = ?",
            (trace_id,),
        ).fetchone()
    assert row is not None
    assert row[0] == 400
    assert row[1] == 150
    assert row[2] == 0
    assert row[3] == 0


def test_sse_empty_terminal_usage_falls_back_to_estimate(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    db, app = _setup(tmp_path, monkeypatch)
    # texts emit "hello", " ", "world" = "hello world" (11 chars); estimate
    # is max(1, 11 // 4) == 2.
    monkeypatch.setattr(
        _anthropic,
        "stream_anthropic_async",
        _stub_stream_anthropic(usage={}, texts=["hello", " ", "world"]),
    )
    with TestClient(app) as client:
        resp = client.post("/api/chat/stream", json={"prompt": "hi", "provider": "anthropic"})
    assert resp.status_code == 200
    trace_id = _trace_id_from_sse(resp.text)
    with sqlite3.connect(str(db.path)) as conn:
        row = conn.execute(
            "SELECT input_tokens, output_tokens FROM llm_calls WHERE trace_id = ?",
            (trace_id,),
        ).fetchone()
    assert row is not None
    assert row[0] == 0
    assert row[1] == 2  # max(1, 11 // 4)


def test_sse_never_persists_zero_for_nonempty_stream(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    db, app = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        _anthropic,
        "stream_anthropic_async",
        _stub_stream_anthropic(usage={}, texts=["non-empty"]),
    )
    with TestClient(app) as client:
        client.post("/api/chat/stream", json={"prompt": "hi", "provider": "anthropic"})
    with sqlite3.connect(str(db.path)) as conn:
        bad = conn.execute(
            "SELECT COUNT(*) FROM llm_calls WHERE input_tokens=0 AND output_tokens=0"
        ).fetchone()[0]
    # Canonical Pitfall 2 warning-sign check from PITFALLS.md line 61.
    assert bad == 0


def test_sse_error_path_publishes_error_event_with_estimated_tokens(
    tmp_path: Path, monkeypatch
) -> None:
    from fastapi.testclient import TestClient

    db, app = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        _anthropic,
        "stream_anthropic_async",
        _stub_stream_anthropic(usage={}, texts=["partial"], raise_after=1),
    )
    with TestClient(app) as client:
        client.post("/api/chat/stream", json={"prompt": "hi", "provider": "anthropic"})
    # Find the error-status llm_calls row and check it has non-zero
    # estimated tokens.
    with sqlite3.connect(str(db.path)) as conn:
        rows = conn.execute("SELECT status, error_type, output_tokens FROM llm_calls").fetchall()
    error_rows = [r for r in rows if r[0] == "error"]
    assert len(error_rows) == 1
    assert error_rows[0][1] == "ConnectionError"
    assert error_rows[0][2] >= 1
