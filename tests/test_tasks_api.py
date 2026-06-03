"""Tests for the tasks/trace-delete API routes and case-insensitive team lookup.

Regression coverage for:
  GET /api/tasks                  -> TasksResponse
  GET /api/tasks?status=<status>  -> filtered TasksResponse
  GET /api/tasks?status=invalid   -> 400 for out-of-allowlist value (CR-03)
  DELETE /api/tasks/{task_id}     -> 204 on success, 404 on missing, 403 non-loopback
  DELETE /api/traces/{trace_id}   -> 204 on success, 404 on missing, 403 non-loopback
  GET /api/team/{slug}            -> case-insensitive slug lookup, traces via profile.name (CR-01)
  GET /api/memory/note            -> is_example field present in response
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from horus_os import Config, Database, create_app
from horus_os.cli.init_cmd import _seed_starter_content
from horus_os.storage import TaskRecord


def _seed(tmp_path: Path) -> Config:
    """Build a fully seeded install (config, db, starter team, demo trace, demo tasks)."""
    cfg = Config.with_defaults(tmp_path)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.notes_dir.mkdir(parents=True, exist_ok=True)
    Database(cfg.db_path).init()
    _seed_starter_content(cfg)
    cfg.save()
    return cfg


def _client(tmp_path: Path) -> TestClient:
    """Loopback client (127.0.0.1) - passes the loopback guard on DELETE endpoints."""
    return TestClient(create_app(data_dir=tmp_path), client=("127.0.0.1", 50000))


def _remote_client(tmp_path: Path) -> TestClient:
    """Non-loopback client (10.0.0.1) - blocked by the loopback guard."""
    return TestClient(create_app(data_dir=tmp_path), client=("10.0.0.1", 50000))


def _seed_extra_tasks(db: Database) -> None:
    """Add a few extra tasks for testing list/filter/delete."""
    db.save_task(
        TaskRecord(
            task_id="test-pending-001",
            title="Test pending task",
            description="A pending task for testing.",
            status="pending",
            agent_profile_name="Coordinator",
            trace_id=None,
            is_demo_seed=False,
            created_at="",
            updated_at="",
        )
    )
    db.save_task(
        TaskRecord(
            task_id="test-completed-001",
            title="Test completed task",
            description="A completed task for testing.",
            status="completed",
            agent_profile_name="Engineer",
            trace_id=None,
            is_demo_seed=False,
            created_at="",
            updated_at="",
        )
    )


# ----------------------------------------------------------------------
# GET /api/tasks
# ----------------------------------------------------------------------


def test_get_tasks_returns_tasks_response_shape(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/tasks")
    assert response.status_code == 200
    payload = response.json()
    assert "tasks" in payload
    assert isinstance(payload["tasks"], list)


def test_get_tasks_includes_seeded_demo_tasks(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/tasks")
    assert response.status_code == 200
    tasks = response.json()["tasks"]
    # Five demo tasks are seeded by _seed_starter_content.
    assert len(tasks) >= 5


def test_get_tasks_row_has_contract_fields(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/tasks")
    assert response.status_code == 200
    tasks = response.json()["tasks"]
    assert len(tasks) > 0
    row = tasks[0]
    assert set(row) == {
        "task_id",
        "title",
        "description",
        "status",
        "agent_profile_name",
        "created_at",
        "updated_at",
    }


def test_get_tasks_status_filter_returns_matching_only(tmp_path: Path) -> None:
    cfg = _seed(tmp_path)
    db = Database(cfg.db_path)
    _seed_extra_tasks(db)

    response = _client(tmp_path).get("/api/tasks", params={"status": "completed"})
    assert response.status_code == 200
    tasks = response.json()["tasks"]
    assert len(tasks) >= 1
    for task in tasks:
        assert task["status"] == "completed"


def test_get_tasks_status_filter_excludes_other_statuses(tmp_path: Path) -> None:
    cfg = _seed(tmp_path)
    db = Database(cfg.db_path)
    _seed_extra_tasks(db)

    response = _client(tmp_path).get("/api/tasks", params={"status": "running"})
    assert response.status_code == 200
    tasks = response.json()["tasks"]
    for task in tasks:
        assert task["status"] == "running"


def test_get_tasks_no_status_filter_returns_all(tmp_path: Path) -> None:
    cfg = _seed(tmp_path)
    db = Database(cfg.db_path)
    _seed_extra_tasks(db)

    all_tasks = _client(tmp_path).get("/api/tasks").json()["tasks"]
    pending_tasks = (
        _client(tmp_path).get("/api/tasks", params={"status": "pending"}).json()["tasks"]
    )
    completed_tasks = (
        _client(tmp_path).get("/api/tasks", params={"status": "completed"}).json()["tasks"]
    )

    # Total should include all statuses (pending + completed at minimum).
    assert len(all_tasks) >= len(pending_tasks) + len(completed_tasks)


# ----------------------------------------------------------------------
# DELETE /api/tasks/{task_id}
# ----------------------------------------------------------------------


def test_delete_task_returns_204(tmp_path: Path) -> None:
    cfg = _seed(tmp_path)
    db = Database(cfg.db_path)
    _seed_extra_tasks(db)

    response = _client(tmp_path).delete("/api/tasks/test-pending-001")
    assert response.status_code == 204


def test_delete_task_removes_the_row(tmp_path: Path) -> None:
    cfg = _seed(tmp_path)
    db = Database(cfg.db_path)
    _seed_extra_tasks(db)

    _client(tmp_path).delete("/api/tasks/test-pending-001")
    tasks_after = db.list_tasks()
    assert not any(t.task_id == "test-pending-001" for t in tasks_after)


def test_delete_task_404_on_missing(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).delete("/api/tasks/does-not-exist-task")
    assert response.status_code == 404


def test_delete_task_double_delete_is_404(tmp_path: Path) -> None:
    cfg = _seed(tmp_path)
    db = Database(cfg.db_path)
    _seed_extra_tasks(db)

    _client(tmp_path).delete("/api/tasks/test-pending-001")
    second = _client(tmp_path).delete("/api/tasks/test-pending-001")
    assert second.status_code == 404


# ----------------------------------------------------------------------
# DELETE /api/traces/{trace_id}
# ----------------------------------------------------------------------


def test_delete_trace_returns_204(tmp_path: Path) -> None:
    cfg = _seed(tmp_path)
    db = Database(cfg.db_path)
    traces = db.list_traces()
    assert len(traces) >= 1
    trace_id = traces[0].trace_id

    response = _client(tmp_path).delete(f"/api/traces/{trace_id}")
    assert response.status_code == 204


def test_delete_trace_removes_the_row(tmp_path: Path) -> None:
    cfg = _seed(tmp_path)
    db = Database(cfg.db_path)
    traces_before = db.list_traces()
    assert len(traces_before) >= 1
    trace_id = traces_before[0].trace_id

    _client(tmp_path).delete(f"/api/traces/{trace_id}")
    traces_after = db.list_traces()
    assert not any(t.trace_id == trace_id for t in traces_after)


def test_delete_trace_404_on_missing(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).delete("/api/traces/no-such-trace-id")
    assert response.status_code == 404


# ----------------------------------------------------------------------
# GET /api/team/{slug} - case-insensitive lookup
# ----------------------------------------------------------------------


def test_team_member_exact_case_still_works(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/team/Coordinator")
    assert response.status_code == 200
    assert response.json()["agent"]["name"] == "Coordinator"


def test_team_member_lowercase_slug_finds_coordinator(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/team/coordinator")
    assert response.status_code == 200
    assert response.json()["agent"]["name"] == "Coordinator"


def test_team_member_lowercase_slug_finds_engineer(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/team/engineer")
    assert response.status_code == 200
    assert response.json()["agent"]["name"] == "Engineer"


def test_team_member_mixed_case_slug_finds_researcher(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/team/RESEARCHER")
    assert response.status_code == 200
    assert response.json()["agent"]["name"] == "Researcher"


def test_team_member_unknown_slug_still_404s(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/team/nobody")
    assert response.status_code == 404


# ----------------------------------------------------------------------
# GET /api/memory/note - is_example field
# ----------------------------------------------------------------------


def test_memory_note_has_is_example_field(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/memory/note", params={"path": "welcome-to-horus-os.md"})
    assert response.status_code == 200
    payload = response.json()
    assert "is_example" in payload


def test_memory_note_seeded_vault_note_is_example_true(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/memory/note", params={"path": "welcome-to-horus-os.md"})
    assert response.status_code == 200
    assert response.json()["is_example"] is True


def test_memory_note_custom_note_is_example_false(tmp_path: Path) -> None:
    cfg = _seed(tmp_path)
    custom = cfg.notes_dir / "my-custom-note.md"
    custom.write_text("# My note\nSome content.\n", encoding="utf-8")

    response = _client(tmp_path).get("/api/memory/note", params={"path": "my-custom-note.md"})
    assert response.status_code == 200
    assert response.json()["is_example"] is False


def test_memory_note_soul_file_is_example_true(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get(
        "/api/memory/note", params={"path": "agents/Coordinator/SOUL.md"}
    )
    assert response.status_code == 200
    assert response.json()["is_example"] is True


# ----------------------------------------------------------------------
# GET /api/tasks?status= - allowlist validation (CR-03)
# ----------------------------------------------------------------------


def test_get_tasks_invalid_status_returns_400(tmp_path: Path) -> None:
    """An out-of-allowlist status value must return 400, not a silent empty list."""
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/tasks", params={"status": "PENDING"})
    assert response.status_code == 400


def test_get_tasks_invalid_status_arbitrary_string_returns_400(tmp_path: Path) -> None:
    """Arbitrary strings that are not valid statuses must return 400."""
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/tasks", params={"status": "notastatus"})
    assert response.status_code == 400


def test_get_tasks_empty_status_returns_all(tmp_path: Path) -> None:
    """An absent or empty status filter still returns all tasks."""
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/tasks")
    assert response.status_code == 200
    assert len(response.json()["tasks"]) >= 5


# ----------------------------------------------------------------------
# DELETE /api/tasks and /api/traces - loopback guard (WR-02)
# ----------------------------------------------------------------------


def test_delete_task_non_loopback_returns_403(tmp_path: Path) -> None:
    """A DELETE from a non-loopback address is refused with 403."""
    cfg = _seed(tmp_path)
    db = Database(cfg.db_path)
    _seed_extra_tasks(db)
    response = _remote_client(tmp_path).delete("/api/tasks/test-pending-001")
    assert response.status_code == 403


def test_delete_trace_non_loopback_returns_403(tmp_path: Path) -> None:
    """A DELETE trace from a non-loopback address is refused with 403."""
    cfg = _seed(tmp_path)
    db = Database(cfg.db_path)
    traces = db.list_traces()
    assert len(traces) >= 1
    trace_id = traces[0].trace_id
    response = _remote_client(tmp_path).delete(f"/api/traces/{trace_id}")
    assert response.status_code == 403


# ----------------------------------------------------------------------
# GET /api/team/{slug} - recent_traces uses profile.name not slug (CR-01)
# ----------------------------------------------------------------------


def test_team_member_slug_returns_traces_seeded_with_canonical_name(tmp_path: Path) -> None:
    """Traces stored as 'Coordinator' must appear when fetching via the lowercase slug."""
    from horus_os.types import AgentResult

    cfg = _seed(tmp_path)
    db = Database(cfg.db_path)
    # Seed an additional trace attributed to the canonical name "Coordinator".
    db.record_trace(
        "Test prompt for coordinator trace",
        AgentResult(
            text="Response text",
            provider="test",
            model="test-model",
        ),
        agent_profile_name="Coordinator",
    )

    # Request via lowercase slug - traces must not be empty.
    response = _client(tmp_path).get("/api/team/coordinator")
    assert response.status_code == 200
    payload = response.json()
    assert payload["agent"]["name"] == "Coordinator"
    # The recent_traces list must contain the trace we seeded (and the demo trace).
    assert len(payload["recent_traces"]) >= 1
    prompts = [t["prompt"] for t in payload["recent_traces"]]
    assert any("coordinator trace" in p for p in prompts), (
        f"expected coordinator trace in recent_traces, got: {prompts}"
    )
