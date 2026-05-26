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
    # Phase 35 DASH-4-04 extension: rollup fields default to zero/null when the
    # agent has no in-window runs.
    assert row["total_runs"] == 0
    assert row["total_cost_usd"] is None
    assert row["latency_p50_ms"] is None
    assert row["latency_p95_ms"] is None
    assert row["uncosted_runs"] == 0


def test_agents_list_preserves_existing_v0_3_keys(tmp_path: Path) -> None:
    """Backward-compat: every key the v0.3 surface returned MUST still be present."""
    _init_db(tmp_path)
    response = _client(tmp_path).get("/api/agents")
    row = response.json()["agents"][0]
    for key in (
        "name",
        "system_prompt",
        "default_model",
        "allowed_tools",
        "memory_scope",
        "created_at",
        "updated_at",
        "last_activity_at",
    ):
        assert key in row, f"missing pre-existing key {key!r}"


def test_agents_list_pre_v0_4_rows_render_null_cost(tmp_path: Path) -> None:
    """Pitfall 11: a synthetic pre-v0.4 trace (total_cost_usd NULL) surfaces as
    total_runs=1, total_cost_usd is None, uncosted_runs=1. NEVER zero dollars."""
    import sqlite3
    import uuid
    from datetime import UTC, datetime

    db = _init_db(tmp_path)
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute(
            "INSERT INTO traces "
            "(trace_id, created_at, provider, model, prompt, response_text, "
            "agent_profile_name, total_input_tokens, total_output_tokens, "
            "total_cost_usd, total_duration_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)",
            (
                uuid.uuid4().hex,
                now_iso,
                "anthropic",
                "claude-sonnet-4-6",
                "p",
                "r",
                "default",
            ),
        )
    response = _client(tmp_path).get("/api/agents")
    row = next(r for r in response.json()["agents"] if r["name"] == "default")
    assert row["total_runs"] == 1
    assert row["total_cost_usd"] is None  # JSON null, NOT 0
    assert row["uncosted_runs"] == 1


def test_agents_list_mixed_v0_3_and_v0_4_rows(tmp_path: Path) -> None:
    """A v0.4 trace at 0.005 + a pre-v0.4 NULL trace -> total_runs=2,
    total_cost_usd=0.005 (sum of non-NULL), uncosted_runs=1."""
    import sqlite3
    import uuid
    from datetime import UTC, datetime

    db = _init_db(tmp_path)
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    with sqlite3.connect(str(db.path)) as conn:
        for cost in (0.005, None):
            conn.execute(
                "INSERT INTO traces "
                "(trace_id, created_at, provider, model, prompt, response_text, "
                "agent_profile_name, total_input_tokens, total_output_tokens, "
                "total_cost_usd) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    uuid.uuid4().hex,
                    now_iso,
                    "anthropic",
                    "claude-sonnet-4-6",
                    "p",
                    "r",
                    "default",
                    100,
                    50,
                    cost,
                ),
            )
    response = _client(tmp_path).get("/api/agents")
    row = next(r for r in response.json()["agents"] if r["name"] == "default")
    assert row["total_runs"] == 2
    assert row["total_cost_usd"] == 0.005
    assert row["uncosted_runs"] == 1


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
