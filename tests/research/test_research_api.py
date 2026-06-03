"""RESEARCH-02: the Deep Research HTTP surface (plan, start, progress, report).

Proves the server half of plan-before-execute and the live progress surface:

  * POST /api/research returns a plan + task_id and writes a 'pending' task row
    WITHOUT running any search or fetch (plan-before-execute);
  * a confirm/start trigger flips the task to 'running' and schedules the
    background orchestrator run; the plan-only call never auto-starts;
  * GET /api/research/{id}/progress reports phase / sources_found /
    iterations_used / iteration_budget, and 404s an unknown task_id;
  * GET /api/research/{id}/report 409s while running and returns the rendered
    markdown once the task is 'completed';
  * the mutating POST routes are refused for a non-loopback client.

run_agent_loop is monkeypatched in every test so no live provider call occurs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from horus_os import Config, Database, create_app
from horus_os.cli.init_cmd import _seed_starter_content
from horus_os.types import AgentResult, ToolResult


def _seed(tmp_path: Path) -> Config:
    cfg = Config.with_defaults(tmp_path)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.notes_dir.mkdir(parents=True, exist_ok=True)
    Database(cfg.db_path).init()
    _seed_starter_content(cfg)
    cfg.save()
    return cfg


def _client(tmp_path: Path) -> TestClient:
    """Loopback client (127.0.0.1) passes the loopback guard on mutating routes."""
    return TestClient(create_app(data_dir=tmp_path), client=("127.0.0.1", 50000))


def _remote_client(tmp_path: Path) -> TestClient:
    """Non-loopback client (10.0.0.1) is blocked by the loopback guard."""
    return TestClient(create_app(data_dir=tmp_path), client=("10.0.0.1", 50000))


def _patch_loop(monkeypatch, surfaced_urls: list[str] | None = None) -> None:
    """Replace run_agent_loop with a stub that drives the source recorder."""
    from horus_os import agent as agent_module

    def _fake_loop(prompt, *, registry, budget=None, on_tool_result=None, **kwargs):
        for url in surfaced_urls or []:
            if on_tool_result is not None:
                on_tool_result(
                    ToolResult(tool_use_id="x", name="analyze_file", output={"url": url})
                )
        return AgentResult(
            text="Findings with a citation [[" + (surfaced_urls or ["https://a.test/1"])[0] + "]].",
            provider="anthropic",
            model="m",
        )

    monkeypatch.setattr(agent_module, "run_agent_loop", _fake_loop)


# ---------------------------------------------------------------------------
# POST /api/research - plan-before-execute
# ---------------------------------------------------------------------------


def test_post_research_returns_plan_and_task_id(tmp_path: Path, monkeypatch) -> None:
    _seed(tmp_path)

    # run_agent_loop must NOT run during a plan-only POST.
    from horus_os import agent as agent_module

    def _boom(*a, **k):  # pragma: no cover - must never run during plan-only
        raise AssertionError("run_agent_loop ran during a plan-only POST /api/research")

    monkeypatch.setattr(agent_module, "run_agent_loop", _boom)

    response = _client(tmp_path).post("/api/research", json={"question": "How safe is X?"})
    assert response.status_code == 200
    body = response.json()
    assert body["task_id"]
    assert body["status"] == "pending"
    assert body["plan"]["question"] == "How safe is X?"
    assert len(body["plan"]["subtopics"]) >= 1
    assert all(sub["query"] for sub in body["plan"]["subtopics"])


def test_post_research_creates_pending_task_row(tmp_path: Path, monkeypatch) -> None:
    cfg = _seed(tmp_path)
    _patch_loop(monkeypatch)
    response = _client(tmp_path).post("/api/research", json={"question": "topic"})
    task_id = response.json()["task_id"]

    db = Database(cfg.db_path)
    rows = {t.task_id: t for t in db.list_tasks(limit=500)}
    assert task_id in rows
    assert rows[task_id].status == "pending"
    assert rows[task_id].trace_id  # a trace_id is linked at plan time


def test_post_research_missing_question_returns_400(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).post("/api/research", json={"question": "   "})
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# start trigger - schedules the background run
# ---------------------------------------------------------------------------


def test_post_research_confirm_flips_to_running(tmp_path: Path, monkeypatch) -> None:
    cfg = _seed(tmp_path)
    _patch_loop(monkeypatch, ["https://a.test/1"])
    response = _client(tmp_path).post("/api/research", json={"question": "topic", "confirm": True})
    assert response.status_code == 200
    assert response.json()["status"] == "running"
    task_id = response.json()["task_id"]
    # The background task runs once the TestClient sends the response; by then
    # the run has completed against the stubbed loop.
    db = Database(cfg.db_path)
    rows = {t.task_id: t for t in db.list_tasks(limit=500)}
    assert rows[task_id].status == "completed"


def test_separate_start_endpoint_runs_the_plan(tmp_path: Path, monkeypatch) -> None:
    cfg = _seed(tmp_path)
    _patch_loop(monkeypatch, ["https://a.test/1"])
    client = _client(tmp_path)
    task_id = client.post("/api/research", json={"question": "topic"}).json()["task_id"]
    # Still pending until an explicit start.
    db = Database(cfg.db_path)
    assert {t.task_id: t for t in db.list_tasks(limit=500)}[task_id].status == "pending"

    started = client.post(f"/api/research/{task_id}/start")
    assert started.status_code == 200
    assert {t.task_id: t for t in db.list_tasks(limit=500)}[task_id].status == "completed"


def test_start_unknown_task_returns_404(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).post("/api/research/no-such-task/start")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/research/{id}/progress
# ---------------------------------------------------------------------------


def test_progress_reports_phase_and_budget(tmp_path: Path, monkeypatch) -> None:
    _seed(tmp_path)
    _patch_loop(monkeypatch)
    client = _client(tmp_path)
    task_id = client.post("/api/research", json={"question": "topic"}).json()["task_id"]
    response = client.get(f"/api/research/{task_id}/progress")
    assert response.status_code == 200
    body = response.json()
    assert body["phase"] in (
        "plan",
        "searching",
        "reading",
        "synthesizing",
        "done",
        "cancelled",
    )
    assert "sources_found" in body
    assert "iterations_used" in body
    # The iteration budget comes from config (default 5).
    assert body["iteration_budget"] >= 1


def test_progress_unknown_task_returns_404(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/research/no-such-task/progress")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/research/{id}/report
# ---------------------------------------------------------------------------


def test_report_409_while_not_completed(tmp_path: Path, monkeypatch) -> None:
    _seed(tmp_path)
    _patch_loop(monkeypatch)
    client = _client(tmp_path)
    task_id = client.post("/api/research", json={"question": "topic"}).json()["task_id"]
    # Still pending (no start) -> report not ready.
    response = client.get(f"/api/research/{task_id}/report")
    assert response.status_code == 409


def test_report_returns_markdown_once_completed(tmp_path: Path, monkeypatch) -> None:
    _seed(tmp_path)
    _patch_loop(monkeypatch, ["https://a.test/1"])
    client = _client(tmp_path)
    task_id = client.post("/api/research", json={"question": "topic", "confirm": True}).json()[
        "task_id"
    ]
    response = client.get(f"/api/research/{task_id}/report")
    assert response.status_code == 200
    body = response.json()
    assert body["report"].startswith("# ")  # rendered markdown H1
    assert body["trace_id"]


def test_report_unknown_task_returns_404(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).get("/api/research/no-such-task/report")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# loopback guard on the mutating routes (T-73-04)
# ---------------------------------------------------------------------------


def test_post_research_non_loopback_returns_403(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _remote_client(tmp_path).post("/api/research", json={"question": "topic"})
    assert response.status_code == 403


def test_start_non_loopback_returns_403(tmp_path: Path, monkeypatch) -> None:
    _seed(tmp_path)
    _patch_loop(monkeypatch)
    # Create a task via a loopback client, then try to start it from a remote one.
    task_id = _client(tmp_path).post("/api/research", json={"question": "topic"}).json()["task_id"]
    response = _remote_client(tmp_path).post(f"/api/research/{task_id}/start")
    assert response.status_code == 403
