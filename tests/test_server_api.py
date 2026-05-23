"""Tests for the FastAPI server endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from horus_os import Database, __version__, create_app
from horus_os.server import api as server_api
from horus_os.types import AgentResult, ToolUse


def _init_db(tmp_path: Path) -> Database:
    from horus_os import Config

    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()
    return db


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(data_dir=tmp_path))


def test_health_endpoint(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_traces_endpoint_returns_empty(tmp_path: Path) -> None:
    _init_db(tmp_path)
    response = _client(tmp_path).get("/api/traces")
    assert response.status_code == 200
    assert response.json() == {"traces": []}


def test_traces_endpoint_returns_recorded(tmp_path: Path) -> None:
    db = _init_db(tmp_path)
    db.record_trace(
        "hi",
        AgentResult(
            text="hello",
            tool_uses=[ToolUse(id="tu_1", name="echo", input={"x": 1})],
            provider="anthropic",
            model="claude-sonnet-4-6",
        ),
    )
    response = _client(tmp_path).get("/api/traces?limit=5")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["traces"]) == 1
    trace = payload["traces"][0]
    assert trace["prompt"] == "hi"
    assert trace["response_text"] == "hello"
    assert trace["tool_uses"][0]["name"] == "echo"


def test_traces_endpoint_503_when_db_missing(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/traces")
    assert response.status_code == 503
    assert "horus-os init" in response.json()["detail"]


def test_get_trace_returns_one(tmp_path: Path) -> None:
    db = _init_db(tmp_path)
    trace_id = db.record_trace(
        "hi", AgentResult(text="ok", provider="anthropic", model="claude-sonnet-4-6")
    )
    response = _client(tmp_path).get(f"/api/traces/{trace_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["trace_id"] == trace_id
    # v0.1-shaped row: both multi-agent fields surface as null.
    assert payload["parent_trace_id"] is None
    assert payload["agent_profile_name"] is None


def test_get_trace_includes_multi_agent_fields(tmp_path: Path) -> None:
    db = _init_db(tmp_path)
    trace_id = db.record_trace(
        "hi",
        AgentResult(text="ok", provider="anthropic", model="claude-sonnet-4-6"),
        parent_trace_id="abc",
        agent_profile_name="terse",
    )
    response = _client(tmp_path).get(f"/api/traces/{trace_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["parent_trace_id"] == "abc"
    assert payload["agent_profile_name"] == "terse"


def test_get_trace_404(tmp_path: Path) -> None:
    _init_db(tmp_path)
    response = _client(tmp_path).get("/api/traces/00000000000000000000000000000000")
    assert response.status_code == 404


def test_get_trace_children_returns_oldest_first(tmp_path: Path) -> None:
    db = _init_db(tmp_path)
    parent_id = db.record_trace("parent", AgentResult(text="p", provider="anthropic", model="m"))
    child_one = db.record_trace(
        "child one",
        AgentResult(text="c1", provider="anthropic", model="m"),
        parent_trace_id=parent_id,
    )
    child_two = db.record_trace(
        "child two",
        AgentResult(text="c2", provider="anthropic", model="m"),
        parent_trace_id=parent_id,
    )
    response = _client(tmp_path).get(f"/api/traces/{parent_id}/children")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["children"]) == 2
    assert payload["children"][0]["trace_id"] == child_one
    assert payload["children"][1]["trace_id"] == child_two


def test_get_trace_children_returns_empty_list(tmp_path: Path) -> None:
    db = _init_db(tmp_path)
    parent_id = db.record_trace("parent", AgentResult(text="p", provider="anthropic", model="m"))
    response = _client(tmp_path).get(f"/api/traces/{parent_id}/children")
    assert response.status_code == 200
    assert response.json() == {"children": []}


def test_get_trace_children_503_when_db_missing(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/traces/anything/children")
    assert response.status_code == 503


def test_writes_endpoint_returns_empty(tmp_path: Path) -> None:
    _init_db(tmp_path)
    response = _client(tmp_path).get("/api/writes")
    assert response.status_code == 200
    assert response.json() == {"writes": []}


def test_writes_endpoint_returns_recorded(tmp_path: Path) -> None:
    db = _init_db(tmp_path)
    db.record_note_write("create", "a.md", 0, 5, "hello")
    response = _client(tmp_path).get("/api/writes?limit=5")
    assert response.status_code == 200
    writes = response.json()["writes"]
    assert len(writes) == 1
    assert writes[0]["operation"] == "create"
    assert writes[0]["rel_path"] == "a.md"


def test_chat_requires_prompt(tmp_path: Path) -> None:
    _init_db(tmp_path)
    response = _client(tmp_path).post("/api/chat", json={"prompt": ""})
    assert response.status_code == 400


def test_chat_503_when_db_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    response = _client(tmp_path).post("/api/chat", json={"prompt": "hi"})
    assert response.status_code == 503


def test_chat_503_when_api_key_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_db(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    response = _client(tmp_path).post("/api/chat", json={"prompt": "hi"})
    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


def test_chat_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_db(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")

    def fake_loop(prompt: str, **kwargs: Any) -> AgentResult:
        return AgentResult(
            text="hello world",
            provider=kwargs["provider"],
            model=kwargs["model"],
            usage={"input_tokens": 1, "output_tokens": 2},
        )

    monkeypatch.setattr(server_api, "run_agent_loop", fake_loop)
    response = _client(tmp_path).post("/api/chat", json={"prompt": "hi"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["text"] == "hello world"
    assert "trace_id" in payload
    assert payload["latency_ms"] >= 0


def test_chat_500_on_provider_error_still_records_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_db(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")

    def boom(*_: Any, **__: Any) -> AgentResult:
        raise RuntimeError("provider down")

    monkeypatch.setattr(server_api, "run_agent_loop", boom)
    response = _client(tmp_path).post("/api/chat", json={"prompt": "hi"})
    assert response.status_code == 500
    assert "provider down" in response.json()["detail"]["error"]
    # Confirm the error trace landed
    from horus_os import Config, Database

    db = Database(Config.with_defaults(tmp_path).db_path)
    traces = db.list_traces()
    assert len(traces) == 1
    assert traces[0].status == "error"


def test_chat_rejects_unknown_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_db(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    response = _client(tmp_path).post("/api/chat", json={"prompt": "hi", "provider": "openai"})
    assert response.status_code == 400


def test_chat_persists_provider_and_model_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_db(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    captured: dict[str, Any] = {}

    def fake_loop(prompt: str, **kwargs: Any) -> AgentResult:
        captured.update(kwargs)
        return AgentResult(text="ok", provider=kwargs["provider"], model=kwargs["model"])

    monkeypatch.setattr(server_api, "run_agent_loop", fake_loop)
    response = _client(tmp_path).post(
        "/api/chat",
        json={"prompt": "hi", "provider": "gemini", "model": "gemini-2.5-pro"},
    )
    assert response.status_code == 200
    assert captured["provider"] == "gemini"
    assert captured["model"] == "gemini-2.5-pro"
