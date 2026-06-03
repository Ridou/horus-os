"""TEST-37: ResearchOrchestrator hard budget enforcement and source de-dup.

This module is the TEST-37 coverage. It proves:

  * the orchestrator constructs the shared IterationBudget as
    IterationBudget(research_max_iterations) and the run stops at or before the
    iteration cap, with budget.remaining never negative (DR-1);
  * the SourceRegistry caps fetched sources at research_max_sources, the
    duplicates de-duplicate, and a budget overrun degrades to a graceful
    partial report that still writes a trace row (RESEARCH-03 / RESEARCH-04);
  * no sub-agent registry contains delegate_to_agent (DR-3);
  * plan() returns subtopics WITHOUT executing search or fetch.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from horus_os import agent as agent_module
from horus_os.config import Config
from horus_os.research.orchestrator import ResearchOrchestrator, ResearchPlan
from horus_os.research.registry import SourceBudgetExceeded
from horus_os.storage import Database
from horus_os.tools.registry import ToolRegistry
from horus_os.types import AgentResult, Tool, ToolResult


def _make_tool(name: str) -> Tool:
    return Tool(
        name=name,
        description=name,
        parameters={"type": "object"},
        handler=lambda **_: name,
    )


def _master_registry() -> ToolRegistry:
    """A master registry holding every builtin a research run might filter to."""
    master = ToolRegistry()
    for name in (
        "web_search",
        "analyze_file",
        "read_file",
        "create_note",
        "append_note",
        "search_notes",
        "read_note",
        "list_notes",
    ):
        master.register(_make_tool(name))
    return master


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test.db")
    database.init()
    return database


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    return Config.with_defaults(tmp_path)


def _orch(db: Database, cfg: Config) -> ResearchOrchestrator:
    return ResearchOrchestrator(
        db,
        _master_registry(),
        notes_store=None,  # the budget/source path never touches notes
        cfg=cfg,
        provider="anthropic",
    )


# ---------------------------------------------------------------------------
# plan() does not execute
# ---------------------------------------------------------------------------


def test_plan_returns_subtopics_without_executing(db: Database, cfg: Config, monkeypatch) -> None:
    called = False

    def _boom(*a, **k):  # pragma: no cover - must never run during plan()
        nonlocal called
        called = True
        raise AssertionError("run_agent_loop must not run during plan()")

    monkeypatch.setattr(agent_module, "run_agent_loop", _boom)
    plan = _orch(db, cfg).plan("How safe is X?")
    assert isinstance(plan, ResearchPlan)
    assert plan.question == "How safe is X?"
    assert len(plan.subtopics) >= 1
    assert all(sub.query for sub in plan.subtopics)
    assert called is False


# ---------------------------------------------------------------------------
# DR-3: no sub-agent registry can delegate
# ---------------------------------------------------------------------------


def test_no_subagent_registry_contains_delegate(db: Database, cfg: Config) -> None:
    registries = _orch(db, cfg).sub_agent_registries()
    assert registries  # the three specialists are present
    for name, reg in registries.items():
        assert "delegate_to_agent" not in reg, f"{name} must not be able to delegate"


# ---------------------------------------------------------------------------
# TEST-37: iteration budget cap
# ---------------------------------------------------------------------------


def test_budget_constructed_from_config_and_caps_iterations(
    db: Database, cfg: Config, monkeypatch
) -> None:
    cfg = replace(cfg, research_max_iterations=2)
    captured = {}

    def _fake_loop(prompt, *, registry, budget=None, **kwargs):
        captured["budget"] = budget
        # A coordinator that keeps delegating: drain the shared budget exactly
        # the way run_agent_loop does (consume once per tool-using turn).
        turns = 0
        while budget.consume():
            turns += 1
        captured["turns"] = turns
        return AgentResult(text="done", provider="anthropic", model="m")

    monkeypatch.setattr(agent_module, "run_agent_loop", _fake_loop)
    _orch(db, cfg).run("q", task_id="t1", parent_trace_id=None)

    budget = captured["budget"]
    # IterationBudget(research_max_iterations) was passed in.
    assert captured["turns"] == 2  # stopped at the cap
    assert budget.remaining == 0  # never negative, never exceeded
    assert budget.consume() is False  # exhausted, cannot exceed the cap


# ---------------------------------------------------------------------------
# TEST-37: source cap + de-dup + graceful partial report
# ---------------------------------------------------------------------------


def test_sources_capped_deduped_and_partial_report(db: Database, cfg: Config, monkeypatch) -> None:
    cfg = replace(cfg, research_max_sources=3, research_max_iterations=10)

    # 5 distinct URLs + 2 duplicates surfaced by a fake fetch path.
    surfaced = [
        "https://a.test/1",
        "https://a.test/2",
        "https://a.test/2",  # duplicate
        "https://a.test/3",
        "https://a.test/1",  # duplicate
        "https://a.test/4",  # 4th distinct -> over the cap of 3
        "https://a.test/5",
    ]

    def _fake_loop(prompt, *, registry, budget=None, on_tool_result=None, **kwargs):
        # Drive the orchestrator's source recorder with fetch-shaped results.
        for url in surfaced:
            on_tool_result(
                ToolResult(
                    tool_use_id="x",
                    name="analyze_file",
                    output={"url": url, "title": "t"},
                )
            )
        return AgentResult(text="done", provider="anthropic", model="m")

    monkeypatch.setattr(agent_module, "run_agent_loop", _fake_loop)
    result = _orch(db, cfg).run("q", task_id="t1", parent_trace_id=None)

    # At most 3 sources; the 2 duplicates de-duplicated; the run degraded
    # gracefully when the 4th distinct source exceeded the cap.
    assert result.sources == 3
    assert result.partial is True
    assert result.report  # a partial report is still produced
    # A trace row is still written for the partial run.
    traces = db.list_traces(limit=10)
    assert any(t.trace_id == result.trace_id for t in traces)


def test_source_recorder_dedup_under_cap(db: Database, cfg: Config, monkeypatch) -> None:
    cfg = replace(cfg, research_max_sources=10, research_max_iterations=10)

    def _fake_loop(prompt, *, registry, budget=None, on_tool_result=None, **kwargs):
        for url in ["https://a.test/x", "https://a.test/x/", "https://A.TEST/x"]:
            on_tool_result(ToolResult(tool_use_id="x", name="analyze_file", output={"url": url}))
        return AgentResult(text="done", provider="anthropic", model="m")

    monkeypatch.setattr(agent_module, "run_agent_loop", _fake_loop)
    result = _orch(db, cfg).run("q", task_id="t1", parent_trace_id=None)
    assert result.sources == 1  # normalized dedup
    assert result.partial is False


def test_register_past_cap_raises_for_caller_reference(db: Database, cfg: Config) -> None:
    # Direct proof the registry refuses overrun even outside the loop path.
    from horus_os.research.registry import SourceRegistry

    reg = SourceRegistry(max_sources=1)
    reg.register_source("https://a.test/1")
    with pytest.raises(SourceBudgetExceeded):
        reg.register_source("https://a.test/2")
