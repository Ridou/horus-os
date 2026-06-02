"""RESEARCH-02 / RESEARCH-05: cancellation at the plan stage and mid-run.

Proves cancel is observed everywhere and never loses observability:

  * POST /api/research/{id}/cancel at the plan stage flips the task status to
    'cancelled';
  * the orchestrator's run loop polls should_cancel between delegation turns
    via a _CancelableBudget, so a cancel requested mid-run halts before the next
    turn; a cancelled run still records a trace row (no silent loss);
  * the _CancelableBudget stops consuming the moment cancel is observed;
  * cancel on a non-loopback client is refused (403);
  * cancel on an unknown task_id returns 404.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from horus_os.config import Config
from horus_os.research.orchestrator import ResearchOrchestrator, _CancelableBudget
from horus_os.storage import Database
from horus_os.tools.registry import ToolRegistry
from horus_os.types import AgentResult, Tool

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from horus_os import create_app
from horus_os.cli.init_cmd import _seed_starter_content

# ---------------------------------------------------------------------------
# orchestrator-level: _CancelableBudget and mid-run halt
# ---------------------------------------------------------------------------


def test_cancelable_budget_stops_consuming_on_cancel() -> None:
    flag = {"cancel": False}
    budget = _CancelableBudget(5, lambda: flag["cancel"])
    assert budget.consume() is True
    assert budget.consume() is True
    flag["cancel"] = True
    # Once cancel is observed, consume() returns False even with budget left.
    assert budget.consume() is False
    assert budget.remaining == 3  # the remaining budget was never spent


def _make_tool(name: str) -> Tool:
    return Tool(
        name=name, description=name, parameters={"type": "object"}, handler=lambda **_: name
    )


def _master_registry() -> ToolRegistry:
    master = ToolRegistry()
    for name in ("web_search", "read_file", "create_note", "search_notes", "read_note"):
        master.register(_make_tool(name))
    return master


def test_orchestrator_run_observes_cancel_and_records_trace(tmp_path: Path, monkeypatch) -> None:
    from horus_os import agent as agent_module

    db = Database(tmp_path / "t.db")
    db.init()
    cfg = Config.with_defaults(tmp_path)

    def _fake_loop(prompt, *, registry, budget=None, **kwargs):
        # A coordinator that keeps delegating: drain the budget. With a cancel
        # already requested, the _CancelableBudget refuses the very first turn.
        turns = 0
        while budget.consume():
            turns += 1
        return AgentResult(text=f"ran {turns} turns", provider="anthropic", model="m")

    monkeypatch.setattr(agent_module, "run_agent_loop", _fake_loop)

    orchestrator = ResearchOrchestrator(
        db, _master_registry(), notes_store=None, cfg=cfg, provider="anthropic"
    )
    result = orchestrator.run(
        "q",
        task_id="t1",
        parent_trace_id=None,
        should_cancel=lambda: True,  # cancel observed immediately
    )
    assert result.cancelled is True
    # A trace row is still written for the cancelled run (no silent loss).
    trace = db.get_trace(result.trace_id)
    assert trace is not None
    assert trace.status == "cancelled"


# ---------------------------------------------------------------------------
# API-level
# ---------------------------------------------------------------------------


def _seed(tmp_path: Path) -> Config:
    cfg = Config.with_defaults(tmp_path)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.notes_dir.mkdir(parents=True, exist_ok=True)
    Database(cfg.db_path).init()
    _seed_starter_content(cfg)
    cfg.save()
    return cfg


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(data_dir=tmp_path), client=("127.0.0.1", 50000))


def _remote_client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(data_dir=tmp_path), client=("10.0.0.1", 50000))


def _patch_loop(monkeypatch) -> None:
    from horus_os import agent as agent_module

    def _fake_loop(prompt, *, registry, budget=None, on_tool_result=None, **kwargs):
        return AgentResult(text="Findings.", provider="anthropic", model="m")

    monkeypatch.setattr(agent_module, "run_agent_loop", _fake_loop)


def test_cancel_at_plan_stage_flips_to_cancelled(tmp_path: Path, monkeypatch) -> None:
    cfg = _seed(tmp_path)
    _patch_loop(monkeypatch)
    client = _client(tmp_path)
    task_id = client.post("/api/research", json={"question": "topic"}).json()["task_id"]

    response = client.post(f"/api/research/{task_id}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"

    db = Database(cfg.db_path)
    assert {t.task_id: t for t in db.list_tasks(limit=500)}[task_id].status == "cancelled"


def test_cancel_sets_the_cancel_flag(tmp_path: Path, monkeypatch) -> None:
    _seed(tmp_path)
    _patch_loop(monkeypatch)
    app = create_app(data_dir=tmp_path)
    client = TestClient(app, client=("127.0.0.1", 50000))
    task_id = client.post("/api/research", json={"question": "topic"}).json()["task_id"]

    client.post(f"/api/research/{task_id}/cancel")
    # The per-task cancel flag the in-flight run polls is set on app.state.
    assert app.state.research_progress[task_id]["cancel_requested"] is True


def test_cancel_unknown_task_returns_404(tmp_path: Path) -> None:
    _seed(tmp_path)
    response = _client(tmp_path).post("/api/research/no-such-task/cancel")
    assert response.status_code == 404


def test_cancel_non_loopback_returns_403(tmp_path: Path, monkeypatch) -> None:
    _seed(tmp_path)
    _patch_loop(monkeypatch)
    task_id = _client(tmp_path).post("/api/research", json={"question": "topic"}).json()["task_id"]
    response = _remote_client(tmp_path).post(f"/api/research/{task_id}/cancel")
    assert response.status_code == 403
