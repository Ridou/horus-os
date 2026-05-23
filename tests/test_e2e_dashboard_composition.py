"""Dashboard composition and v0.1-database-on-disk tests.

Phase 19 gaps E and F:

- Phase 16 tested `/api/chat/stream` and `/api/agents` separately. No
  test verifies that an SSE chat with an `agent` parameter then surfaces
  the trace in the corresponding `last_activity_at` field. This file
  closes that seam.
- Phase 12 + 13 tested the v1-to-v4 schema migration at the storage
  layer. No test takes a v1-shaped database off disk, lets the
  dashboard open it via `create_app(data_dir)`, and confirms `/api/traces`
  and `/api/agents` work transparently.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from horus_os import AgentProfile, Config, Database, create_app
from horus_os.server import api as server_api


def _init_db(tmp_path: Path) -> Database:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()
    return db


def _frames(body: bytes) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for part in body.split(b"\n\n"):
        line = part.strip()
        if not line.startswith(b"data: "):
            continue
        out.append(json.loads(line[len(b"data: ") :].decode("utf-8")))
    return out


# ---------------------------------------------------------------------------
# Gap E: SSE chat -> agents last_activity composition
# ---------------------------------------------------------------------------


def test_sse_chat_with_agent_updates_last_activity_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An SSE chat with `agent=X` records a trace tagged with the
    profile name. Subsequent /api/agents calls surface that activity
    as `last_activity_at` for X.

    Closes the cross-feature seam between the streaming chat
    endpoint and the agents list's `last_activity_at` computation.
    """
    db = _init_db(tmp_path)
    db.save_profile(
        AgentProfile(
            name="terse",
            system_prompt="be terse",
            default_model="claude-sonnet-4-6",
        )
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")

    async def fake_stream(prompt: str, **_: Any) -> Any:
        yield "ok"

    monkeypatch.setattr(server_api, "run_agent_stream", fake_stream)
    client = TestClient(create_app(data_dir=tmp_path))

    before = client.get("/api/agents").json()
    terse_before = next(a for a in before["agents"] if a["name"] == "terse")
    assert terse_before["last_activity_at"] is None

    response = client.post("/api/chat/stream", json={"prompt": "hi", "agent": "terse"})
    assert response.status_code == 200
    frames = _frames(response.content)
    done_frames = [f for f in frames if f["type"] == "done"]
    assert len(done_frames) == 1
    trace_id = done_frames[0]["trace_id"]

    after = client.get("/api/agents").json()
    terse_after = next(a for a in after["agents"] if a["name"] == "terse")
    assert terse_after["last_activity_at"] is not None
    # And the trace itself is reachable via /api/traces/{id}.
    trace = client.get(f"/api/traces/{trace_id}").json()
    assert trace["agent_profile_name"] == "terse"
    # Created-at on the trace matches the agents-list last_activity_at.
    assert terse_after["last_activity_at"] == trace["created_at"]


# ---------------------------------------------------------------------------
# Gap F: v0.1 database on disk through the dashboard
# ---------------------------------------------------------------------------


_V1_DDL = """
CREATE TABLE schema_version (version INTEGER NOT NULL PRIMARY KEY);
INSERT INTO schema_version (version) VALUES (1);
CREATE TABLE traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt TEXT NOT NULL,
    response_text TEXT NOT NULL DEFAULT '',
    tool_uses TEXT NOT NULL DEFAULT '[]',
    usage TEXT NOT NULL DEFAULT '{}',
    latency_ms INTEGER,
    status TEXT NOT NULL DEFAULT 'success',
    error_message TEXT
);
INSERT INTO traces (trace_id, created_at, provider, model, prompt, response_text)
    VALUES (
        '0123456789abcdef0123456789abcdef',
        '2026-01-01T00:00:00Z',
        'anthropic',
        'claude-sonnet-4-6',
        'legacy v1 prompt',
        'legacy v1 response'
    );
"""


def _write_v1_db(tmp_path: Path) -> Path:
    """Write a v1-shaped sqlite file at the default db_path location."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "horus.sqlite"
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(_V1_DDL)
    return db_path


def test_v01_database_on_disk_renders_through_dashboard(tmp_path: Path) -> None:
    """A v0.1-shaped sqlite file on disk, after `Database.init()`
    runs the v1->v4 migration, surfaces via /api/traces with both
    new columns reported as null.

    This is the realistic post-upgrade path: the user installed
    v0.2, ran `horus-os init` against the existing data_dir, and
    opens the dashboard. The legacy trace must render.
    """
    db_path = _write_v1_db(tmp_path)
    # Simulate `horus-os init` running the migration on the existing db.
    Database(db_path).init()

    # Sanity: the migration bumped the schema.
    with sqlite3.connect(str(db_path)) as conn:
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert version == 4

    client = TestClient(create_app(data_dir=tmp_path))
    response = client.get("/api/traces")
    assert response.status_code == 200
    traces = response.json()["traces"]
    assert len(traces) == 1
    legacy = traces[0]
    assert legacy["trace_id"] == "0123456789abcdef0123456789abcdef"
    assert legacy["prompt"] == "legacy v1 prompt"
    assert legacy["response_text"] == "legacy v1 response"
    # The new v0.2 fields surface as null for legacy rows.
    assert legacy["parent_trace_id"] is None
    assert legacy["agent_profile_name"] is None


def test_v01_database_on_disk_seeds_default_agent_through_dashboard(tmp_path: Path) -> None:
    """After the v1->v4 migration runs on an existing database, the
    default agent profile is bootstrapped and surfaces via /api/agents.

    Closes the seam between the agent_profiles bootstrap (Phase 12)
    and the dashboard list route (Phase 16): a v0.1 database had no
    agent_profiles table, so the upgrade must add the table AND seed
    the default row.
    """
    db_path = _write_v1_db(tmp_path)
    Database(db_path).init()

    client = TestClient(create_app(data_dir=tmp_path))
    response = client.get("/api/agents")
    assert response.status_code == 200
    agents = response.json()["agents"]
    names = {a["name"] for a in agents}
    assert "default" in names
    default = next(a for a in agents if a["name"] == "default")
    # The v0.1 trace was not tagged with an agent, so the default
    # profile reports no activity.
    assert default["last_activity_at"] is None


def test_v01_database_on_disk_children_route_works_on_legacy_trace(
    tmp_path: Path,
) -> None:
    """Asking the /children route for a legacy v0.1 trace returns an
    empty children list (no parent linkage existed before v4) rather
    than a 500.

    This is the defensive contract that the dashboard's expand
    affordance is safe to invoke on every trace, even ones that
    pre-date the multi-agent surface.
    """
    db_path = _write_v1_db(tmp_path)
    Database(db_path).init()

    client = TestClient(create_app(data_dir=tmp_path))
    response = client.get("/api/traces/0123456789abcdef0123456789abcdef/children")
    assert response.status_code == 200
    assert response.json() == {"children": []}
