"""Tests for the read-only v0.7 dashboard JSON surface.

These boot a FastAPI ``TestClient`` against a ``create_app`` built on a
temp data dir seeded with the starter team (the same content a fresh
``horus-os init`` writes). They assert the response shapes match
``frontend/lib/types.ts`` exactly and that ``/api/settings`` never leaks
a secret-like value.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from horus_os import Config, Database, __version__, create_app
from horus_os.cli.init_cmd import _seed_starter_content
from horus_os.seed import STARTER_TEAM

STARTER_NAMES = {entry["name"] for entry in STARTER_TEAM}


def _seed(tmp_path: Path) -> Config:
    """Build a fully seeded install (config, db, starter team, demo trace)."""
    cfg = Config.with_defaults(tmp_path)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.notes_dir.mkdir(parents=True, exist_ok=True)
    Database(cfg.db_path).init()
    _seed_starter_content(cfg)
    cfg.save()
    return cfg


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(data_dir=tmp_path))


# ----------------------------------------------------------------------
# /api/team
# ----------------------------------------------------------------------


def test_team_returns_starter_agents(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/team")
    assert response.status_code == 200
    payload = response.json()
    agents = {a["name"]: a for a in payload["agents"]}
    # The five starter agents are present (plus the seeded 'default' profile).
    assert STARTER_NAMES <= set(agents)

    coordinator = agents["Coordinator"]
    # Contract field set from frontend/lib/types.ts::Agent, exact keys.
    assert set(coordinator) == {
        "name",
        "color",
        "description",
        "default_model",
        "soul_path",
        "status",
        "trace_count",
        "last_active_at",
    }
    assert coordinator["color"] == "#00d4ff"
    assert coordinator["soul_path"] == "agents/Coordinator/SOUL.md"
    # The demo trace is attributed to the Coordinator, so it is counted.
    assert coordinator["trace_count"] == 1
    assert coordinator["last_active_at"] is not None
    # A trace exists from "now", so the Coordinator reads as active.
    assert coordinator["status"] == "active"

    # An agent with no traces reads idle with a zero count and null timestamp.
    engineer = agents["Engineer"]
    assert engineer["trace_count"] == 0
    assert engineer["last_active_at"] is None
    assert engineer["status"] == "idle"


# ----------------------------------------------------------------------
# /api/team/{name}
# ----------------------------------------------------------------------


def test_team_member_detail(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/team/Coordinator")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"agent", "soul_markdown", "recent_traces"}

    agent = payload["agent"]
    # AgentDetail extends Agent with system_prompt.
    assert set(agent) == {
        "name",
        "color",
        "description",
        "default_model",
        "soul_path",
        "status",
        "trace_count",
        "last_active_at",
        "system_prompt",
    }
    assert agent["name"] == "Coordinator"
    assert agent["system_prompt"]

    # The seeded SOUL.md persona is resolved from notes_dir / soul_path.
    assert payload["soul_markdown"] is not None
    assert "#" in payload["soul_markdown"]

    # recent_traces carries the demo trace with the contract field set.
    assert len(payload["recent_traces"]) == 1
    trace = payload["recent_traces"][0]
    assert set(trace) == {"trace_id", "created_at", "prompt", "status"}
    assert trace["prompt"] == "How do I get started with horus-os?"


def test_team_member_404_on_unknown(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/team/Nobody")
    assert response.status_code == 404


def test_team_member_soul_null_when_unset(tmp_path: Path) -> None:
    """An agent profile with no SOUL.md file gets a null soul_markdown."""
    cfg = _seed(tmp_path)
    # Remove the Coordinator's persona file; the route must fall back to null.
    soul_file = cfg.notes_dir / "agents" / "Coordinator" / "SOUL.md"
    soul_file.unlink()
    response = _client(tmp_path).get("/api/team/Coordinator")
    assert response.status_code == 200
    assert response.json()["soul_markdown"] is None


# ----------------------------------------------------------------------
# /api/memory
# ----------------------------------------------------------------------


def test_memory_lists_seeded_notes(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/memory")
    assert response.status_code == 200
    notes = response.json()["notes"]
    paths = {n["path"] for n in notes}
    assert "welcome-to-horus-os.md" in paths

    welcome = next(n for n in notes if n["path"] == "welcome-to-horus-os.md")
    assert set(welcome) == {"path", "title", "size_bytes", "modified_at", "preview"}
    assert welcome["title"] == "Welcome to horus-os"
    assert welcome["size_bytes"] > 0


def test_memory_search_filters(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/memory", params={"q": "Welcome to horus-os"})
    assert response.status_code == 200
    notes = response.json()["notes"]
    assert notes  # at least one hit
    assert all("path" in n for n in notes)
    # The welcome note is the strongest match for that query.
    assert any(n["path"] == "welcome-to-horus-os.md" for n in notes)


# ----------------------------------------------------------------------
# /api/memory/note
# ----------------------------------------------------------------------


def test_memory_note_returns_markdown(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/memory/note", params={"path": "welcome-to-horus-os.md"})
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"path", "title", "markdown", "modified_at", "is_example"}
    assert payload["path"] == "welcome-to-horus-os.md"
    assert payload["title"] == "Welcome to horus-os"
    assert payload["markdown"].startswith("# Welcome to horus-os")


def test_memory_note_404_on_missing(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/memory/note", params={"path": "does-not-exist.md"})
    assert response.status_code == 404


def test_memory_note_rejects_path_traversal(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/memory/note", params={"path": "../../../../etc/passwd"})
    assert response.status_code == 400


# ----------------------------------------------------------------------
# /api/activity
# ----------------------------------------------------------------------


def test_activity_returns_demo_event(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/activity")
    assert response.status_code == 200
    events = response.json()["events"]
    assert len(events) == 1
    event = events[0]
    assert set(event) == {"trace_id", "created_at", "agent", "kind", "summary", "status"}
    assert event["agent"] == "Coordinator"
    assert event["kind"] == "agent_run"
    assert event["summary"].startswith("How do I get started")


def test_activity_respects_limit(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/activity", params={"limit": 0})
    assert response.status_code == 200
    # limit is clamped to at least 1; with one seeded trace that returns it.
    assert len(response.json()["events"]) == 1


# ----------------------------------------------------------------------
# /api/health
# ----------------------------------------------------------------------


def test_health_reports_counts(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "status",
        "version",
        "db_size_bytes",
        "trace_count",
        "note_count",
        "agent_count",
    }
    assert payload["status"] == "ok"
    assert payload["version"] == __version__
    assert payload["db_size_bytes"] > 0
    assert payload["trace_count"] == 1
    assert payload["note_count"] > 0
    # Five starter agents plus the seeded 'default' profile.
    assert payload["agent_count"] == len(STARTER_NAMES) + 1


# ----------------------------------------------------------------------
# /api/settings
# ----------------------------------------------------------------------


def test_settings_returns_config_without_secrets(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/settings")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "data_dir",
        "notes_dir",
        "db_path",
        "default_provider",
        "anthropic_model",
        "gemini_model",
        "schema_version",
        "version",
        "counts",
    }
    assert set(payload["counts"]) == {"agents", "notes", "traces"}
    assert payload["counts"]["traces"] == 1
    assert payload["counts"]["agents"] == len(STARTER_NAMES) + 1
    assert payload["default_provider"] == "anthropic"
    assert payload["version"] == __version__

    # No secret-like key anywhere in the response, at any nesting level.
    blob = str(payload).lower()
    for forbidden in (
        "api_key",
        "apikey",
        "secret",
        "token",
        "password",
        "anthropic_api",
        "gemini_api",
    ):
        assert forbidden not in blob
