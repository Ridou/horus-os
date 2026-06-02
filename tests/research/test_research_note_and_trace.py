"""RESEARCH-05: a completed run leaves an audited note and an inspectable trace.

Proves the audit-and-observability half of the research API:

  * a completed run writes the cited report via NotesStore.create_note under
    research/<task_id>.md, and the write is recorded in note_writes (audited),
    provable by reading the note back and by the recorded write row;
  * the task row's trace_id matches a real traces row produced by the run, so
    GET /api/traces/{trace_id} resolves it; the task status is 'completed';
  * a source-budget overrun (SourceBudgetExceeded from 73-01) finishes as a
    graceful partial report with status 'completed' and still writes the note +
    trace (DR-1).

run_agent_loop is monkeypatched so no live provider call occurs.
"""

from __future__ import annotations

from dataclasses import replace
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
    return TestClient(create_app(data_dir=tmp_path), client=("127.0.0.1", 50000))


def _patch_loop(monkeypatch, surfaced_urls: list[str]) -> None:
    from horus_os import agent as agent_module

    cited = surfaced_urls[0] if surfaced_urls else "https://a.test/1"

    def _fake_loop(prompt, *, registry, budget=None, on_tool_result=None, **kwargs):
        for url in surfaced_urls:
            if on_tool_result is not None:
                on_tool_result(
                    ToolResult(tool_use_id="x", name="analyze_file", output={"url": url})
                )
        return AgentResult(
            text=f"Findings citing [[{cited}]].",
            provider="anthropic",
            model="m",
        )

    monkeypatch.setattr(agent_module, "run_agent_loop", _fake_loop)


def _run_to_completion(client: TestClient, question: str = "topic") -> str:
    return client.post("/api/research", json={"question": question, "confirm": True}).json()[
        "task_id"
    ]


# ---------------------------------------------------------------------------
# audited note
# ---------------------------------------------------------------------------


def test_completed_run_writes_report_as_note(tmp_path: Path, monkeypatch) -> None:
    cfg = _seed(tmp_path)
    _patch_loop(monkeypatch, ["https://a.test/1"])
    task_id = _run_to_completion(_client(tmp_path))

    note_path = cfg.notes_dir / "research" / f"{task_id}.md"
    assert note_path.is_file()
    assert note_path.read_text().startswith("# ")


def test_report_note_write_is_audited(tmp_path: Path, monkeypatch) -> None:
    cfg = _seed(tmp_path)
    _patch_loop(monkeypatch, ["https://a.test/1"])
    task_id = _run_to_completion(_client(tmp_path))

    db = Database(cfg.db_path)
    writes = db.list_note_writes(limit=200)
    rel = f"research/{task_id}.md"
    assert any(w.rel_path == rel and w.operation == "create" for w in writes)


# ---------------------------------------------------------------------------
# inspectable trace + completed status
# ---------------------------------------------------------------------------


def test_task_trace_id_resolves_in_traces_route(tmp_path: Path, monkeypatch) -> None:
    cfg = _seed(tmp_path)
    _patch_loop(monkeypatch, ["https://a.test/1"])
    client = _client(tmp_path)
    task_id = _run_to_completion(client)

    db = Database(cfg.db_path)
    task = {t.task_id: t for t in db.list_tasks(limit=500)}[task_id]
    assert task.status == "completed"
    assert task.trace_id

    # The pre-generated trace_id resolves a real traces row via /api/traces.
    response = client.get(f"/api/traces/{task.trace_id}")
    assert response.status_code == 200
    assert response.json()["trace_id"] == task.trace_id


def test_trace_row_recorded_under_pregenerated_id(tmp_path: Path, monkeypatch) -> None:
    cfg = _seed(tmp_path)
    _patch_loop(monkeypatch, ["https://a.test/1"])
    task_id = _run_to_completion(_client(tmp_path))

    db = Database(cfg.db_path)
    task = {t.task_id: t for t in db.list_tasks(limit=500)}[task_id]
    trace = db.get_trace(task.trace_id)
    assert trace is not None
    assert trace.agent_profile_name == "Research Coordinator"


# ---------------------------------------------------------------------------
# DR-1: source-budget overrun still completes with note + trace
# ---------------------------------------------------------------------------


def test_source_budget_overrun_still_writes_note_and_trace(tmp_path: Path, monkeypatch) -> None:
    cfg = _seed(tmp_path)
    # Cap sources at 2 and surface 3 distinct so the 3rd raises
    # SourceBudgetExceeded inside the orchestrator's source recorder. The cap
    # is persisted to config.toml so the background run's Config.load reads it.
    replace(cfg, research_max_sources=2).save()
    _patch_loop(monkeypatch, ["https://a.test/1", "https://a.test/2", "https://a.test/3"])

    task_id = _run_to_completion(_client(tmp_path))

    db = Database(cfg.db_path)
    task = {t.task_id: t for t in db.list_tasks(limit=500)}[task_id]
    # A graceful partial still completes (the report landed as a note).
    assert task.status == "completed"
    note_path = cfg.notes_dir / "research" / f"{task_id}.md"
    assert note_path.is_file()
    # A trace row is still written for the partial run (DR-1, no silent loss).
    assert db.get_trace(task.trace_id) is not None
