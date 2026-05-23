"""Tests for the SSE /api/chat/stream route."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from horus_os import Database, create_app
from horus_os.server import api as server_api
from horus_os.types import ToolCallEvent


def _init_db(tmp_path: Path) -> Database:
    from horus_os import Config

    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()
    return db


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(data_dir=tmp_path))


def _frames(body: bytes) -> list[dict[str, Any]]:
    """Decode every SSE `data: <json>` frame in the response body."""
    out: list[dict[str, Any]] = []
    for part in body.split(b"\n\n"):
        line = part.strip()
        if not line.startswith(b"data: "):
            continue
        out.append(json.loads(line[len(b"data: ") :].decode("utf-8")))
    return out


def _make_fake_stream(captured: dict[str, Any], tokens: list[str]):
    async def fake_stream(prompt, *, provider, model, max_tokens=1024, system=None):
        captured["prompt"] = prompt
        captured["provider"] = provider
        captured["model"] = model
        captured["system"] = system
        for token in tokens:
            yield token

    return fake_stream


def test_stream_requires_prompt(tmp_path: Path) -> None:
    _init_db(tmp_path)
    response = _client(tmp_path).post("/api/chat/stream", json={"prompt": ""})
    assert response.status_code == 400


def test_stream_503_when_db_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    response = _client(tmp_path).post("/api/chat/stream", json={"prompt": "hi"})
    assert response.status_code == 503


def test_stream_503_when_api_key_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_db(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    response = _client(tmp_path).post("/api/chat/stream", json={"prompt": "hi"})
    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


def test_stream_rejects_unknown_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_db(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    response = _client(tmp_path).post(
        "/api/chat/stream", json={"prompt": "hi", "provider": "openai"}
    )
    assert response.status_code == 400


def test_stream_404_when_agent_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_db(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    response = _client(tmp_path).post("/api/chat/stream", json={"prompt": "hi", "agent": "ghost"})
    assert response.status_code == 404
    assert "ghost" in response.json()["detail"]


def test_stream_happy_path_token_frames(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_db(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        server_api,
        "run_agent_stream",
        _make_fake_stream(captured, ["Hello", ", ", "world"]),
    )
    response = _client(tmp_path).post("/api/chat/stream", json={"prompt": "hi"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = _frames(response.content)
    token_frames = [f for f in frames if f["type"] == "token"]
    done_frames = [f for f in frames if f["type"] == "done"]
    assert len(token_frames) == 3
    assert "".join(f["text"] for f in token_frames) == "Hello, world"
    assert len(done_frames) == 1
    assert done_frames[0]["trace_id"]
    assert done_frames[0]["latency_ms"] >= 0
    assert captured["prompt"] == "hi"
    assert captured["provider"] == "anthropic"

    db = Database(tmp_path / "horus.sqlite")
    traces = db.list_traces()
    assert len(traces) == 1
    assert traces[0].response_text == "Hello, world"
    assert traces[0].status == "success"
    assert traces[0].agent_profile_name is None


def test_stream_emits_tool_call_frame(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_db(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")

    async def fake_stream(prompt, *, provider, model, max_tokens=1024, system=None):
        yield "hi"
        yield ToolCallEvent(name="read_file", input={"path": "a"})

    monkeypatch.setattr(server_api, "run_agent_stream", fake_stream)
    response = _client(tmp_path).post("/api/chat/stream", json={"prompt": "hi"})
    assert response.status_code == 200
    frames = _frames(response.content)
    tool_frames = [f for f in frames if f["type"] == "tool_call"]
    done_frames = [f for f in frames if f["type"] == "done"]
    assert len(tool_frames) == 1
    assert tool_frames[0]["name"] == "read_file"
    assert tool_frames[0]["input"] == {"path": "a"}
    assert len(done_frames) == 1


def test_stream_emits_error_frame_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_db(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")

    async def fake_stream(prompt, *, provider, model, max_tokens=1024, system=None):
        yield "hi"
        raise RuntimeError("provider down")

    monkeypatch.setattr(server_api, "run_agent_stream", fake_stream)
    response = _client(tmp_path).post("/api/chat/stream", json={"prompt": "hi"})
    assert response.status_code == 200
    frames = _frames(response.content)
    error_frames = [f for f in frames if f["type"] == "error"]
    done_frames = [f for f in frames if f["type"] == "done"]
    assert len(error_frames) == 1
    assert "provider down" in error_frames[0]["message"]
    assert error_frames[0]["trace_id"]
    assert done_frames == []

    db = Database(tmp_path / "horus.sqlite")
    traces = db.list_traces()
    assert len(traces) == 1
    assert traces[0].status == "error"
    assert traces[0].response_text == "hi"
    assert "provider down" in (traces[0].error_message or "")


def test_stream_forwards_agent_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _init_db(tmp_path)
    from horus_os.types import AgentProfile

    db.save_profile(
        AgentProfile(
            name="terse",
            system_prompt="be terse",
            default_model="claude-sonnet-4-6",
        )
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    captured: dict[str, Any] = {}
    monkeypatch.setattr(server_api, "run_agent_stream", _make_fake_stream(captured, ["ok"]))
    response = _client(tmp_path).post("/api/chat/stream", json={"prompt": "hi", "agent": "terse"})
    assert response.status_code == 200
    assert captured["system"] == "be terse"
    assert captured["model"] == "claude-sonnet-4-6"

    traces = db.list_traces()
    assert len(traces) == 1
    assert traces[0].agent_profile_name == "terse"


def test_stream_user_model_wins_over_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _init_db(tmp_path)
    from horus_os.types import AgentProfile

    db.save_profile(
        AgentProfile(name="terse", system_prompt="be terse", default_model="claude-sonnet-4-6")
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    captured: dict[str, Any] = {}
    monkeypatch.setattr(server_api, "run_agent_stream", _make_fake_stream(captured, ["ok"]))
    response = _client(tmp_path).post(
        "/api/chat/stream",
        json={"prompt": "hi", "agent": "terse", "model": "override-m"},
    )
    assert response.status_code == 200
    assert captured["model"] == "override-m"
