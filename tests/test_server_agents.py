"""Tests for the agents CRUD routes."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from horus_os import Database, create_app
from horus_os.types import AgentResult


def _init_db(tmp_path: Path) -> Database:
    from horus_os import Config

    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()
    return db


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(data_dir=tmp_path))


def test_agents_list_returns_default_after_init(tmp_path: Path) -> None:
    _init_db(tmp_path)
    response = _client(tmp_path).get("/api/agents")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["agents"]) == 1
    row = payload["agents"][0]
    assert row["name"] == "default"
    assert row["default_model"] is None
    assert row["allowed_tools"] is None
    assert row["last_activity_at"] is None
    assert row["system_prompt"]


def test_agents_list_503_when_db_missing(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/agents")
    assert response.status_code == 503


def test_agents_show_returns_one(tmp_path: Path) -> None:
    _init_db(tmp_path)
    response = _client(tmp_path).get("/api/agents/default")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "default"
    assert "system_prompt" in payload


def test_agents_show_404(tmp_path: Path) -> None:
    _init_db(tmp_path)
    response = _client(tmp_path).get("/api/agents/ghost")
    assert response.status_code == 404
    assert "ghost" in response.json()["detail"]


def test_agents_create_round_trip(tmp_path: Path) -> None:
    _init_db(tmp_path)
    client = _client(tmp_path)
    response = client.post(
        "/api/agents",
        json={
            "name": "foo",
            "system_prompt": "be terse",
            "default_model": "claude-sonnet-4-6",
            "allowed_tools": ["read_file", "list_notes"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "foo"
    assert payload["default_model"] == "claude-sonnet-4-6"
    assert payload["allowed_tools"] == ["read_file", "list_notes"]
    assert payload["last_activity_at"] is None

    listing = client.get("/api/agents").json()["agents"]
    names = [row["name"] for row in listing]
    assert "foo" in names

    shown = client.get("/api/agents/foo").json()
    assert shown["system_prompt"] == "be terse"
    assert shown["allowed_tools"] == ["read_file", "list_notes"]


def test_agents_create_duplicate_returns_409(tmp_path: Path) -> None:
    _init_db(tmp_path)
    client = _client(tmp_path)
    body = {"name": "foo", "system_prompt": "p"}
    assert client.post("/api/agents", json=body).status_code == 200
    second = client.post("/api/agents", json=body)
    assert second.status_code == 409
    assert "already exists" in second.json()["detail"]


def test_agents_create_400_missing_fields(tmp_path: Path) -> None:
    _init_db(tmp_path)
    client = _client(tmp_path)
    assert client.post("/api/agents", json={}).status_code == 400
    assert client.post("/api/agents", json={"name": ""}).status_code == 400
    assert client.post("/api/agents", json={"name": "x"}).status_code == 400


def test_agents_create_400_allowed_tools_not_list(tmp_path: Path) -> None:
    _init_db(tmp_path)
    response = _client(tmp_path).post(
        "/api/agents",
        json={"name": "x", "system_prompt": "p", "allowed_tools": "read_file"},
    )
    assert response.status_code == 400


def test_agents_edit_partial_update(tmp_path: Path) -> None:
    _init_db(tmp_path)
    client = _client(tmp_path)
    client.post(
        "/api/agents",
        json={"name": "foo", "system_prompt": "original", "default_model": "m1"},
    )
    response = client.patch("/api/agents/foo", json={"default_model": "m2"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["system_prompt"] == "original"
    assert payload["default_model"] == "m2"


def test_agents_edit_clear_allowed_tools(tmp_path: Path) -> None:
    _init_db(tmp_path)
    client = _client(tmp_path)
    client.post(
        "/api/agents",
        json={"name": "foo", "system_prompt": "p", "allowed_tools": ["a"]},
    )
    response = client.patch("/api/agents/foo", json={"allowed_tools": None})
    assert response.status_code == 200
    assert response.json()["allowed_tools"] is None


def test_agents_edit_404(tmp_path: Path) -> None:
    _init_db(tmp_path)
    response = _client(tmp_path).patch("/api/agents/ghost", json={"default_model": "m"})
    assert response.status_code == 404


def test_agents_edit_400_invalid_allowed_tools(tmp_path: Path) -> None:
    _init_db(tmp_path)
    client = _client(tmp_path)
    client.post("/api/agents", json={"name": "foo", "system_prompt": "p"})
    response = client.patch("/api/agents/foo", json={"allowed_tools": "not-a-list"})
    assert response.status_code == 400


def test_agents_delete_round_trip(tmp_path: Path) -> None:
    _init_db(tmp_path)
    client = _client(tmp_path)
    client.post("/api/agents", json={"name": "foo", "system_prompt": "p"})
    response = client.delete("/api/agents/foo")
    assert response.status_code == 204

    listing = client.get("/api/agents").json()["agents"]
    names = [row["name"] for row in listing]
    assert "foo" not in names


def test_agents_delete_404(tmp_path: Path) -> None:
    _init_db(tmp_path)
    response = _client(tmp_path).delete("/api/agents/ghost")
    assert response.status_code == 404


def test_agents_last_activity_at_reflects_trace_creation(tmp_path: Path) -> None:
    db = _init_db(tmp_path)
    db.record_trace(
        "hi",
        AgentResult(text="ok", provider="anthropic", model="claude-sonnet-4-6"),
        agent_profile_name="default",
    )
    response = _client(tmp_path).get("/api/agents")
    assert response.status_code == 200
    row = next(r for r in response.json()["agents"] if r["name"] == "default")
    assert row["last_activity_at"] is not None
    assert row["last_activity_at"].endswith("Z")
