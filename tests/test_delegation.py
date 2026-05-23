"""Tests for delegation primitives and the delegate_to_agent tool."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest

from horus_os import AgentProfile, AgentResult, Database
from horus_os.tools import delegation as delegation_module
from horus_os.tools.delegation import IterationBudget, _filter_registry, make_delegate_tool
from horus_os.tools.loop import execute_tool_uses
from horus_os.tools.registry import ToolRegistry
from horus_os.types import Tool, ToolUse


def _make_tool(name: str) -> Tool:
    return Tool(
        name=name,
        description=name,
        parameters={"type": "object"},
        handler=lambda **_: name,
    )


# ---------------------------------------------------------------------------
# IterationBudget
# ---------------------------------------------------------------------------


def test_iteration_budget_consume_returns_true_until_exhausted() -> None:
    budget = IterationBudget(3)
    assert budget.consume() is True
    assert budget.consume() is True
    assert budget.consume() is True
    assert budget.consume() is False


def test_iteration_budget_zero_returns_false_on_first_consume() -> None:
    budget = IterationBudget(0)
    assert budget.consume() is False


def test_iteration_budget_remaining_reflects_decrements() -> None:
    budget = IterationBudget(5)
    assert budget.remaining == 5
    budget.consume()
    assert budget.remaining == 4
    budget.consume()
    budget.consume()
    assert budget.remaining == 2


def test_iteration_budget_negative_initial_is_exhausted() -> None:
    # Defensive: a caller passing a negative value should still see "exhausted".
    budget = IterationBudget(-1)
    assert budget.consume() is False
    assert budget.remaining == -1


def test_iteration_budget_thread_safety_no_double_count() -> None:
    """Two threads racing on consume() never together drain past the budget."""
    budget = IterationBudget(1000)
    results: list[bool] = []
    results_lock = threading.Lock()

    def worker() -> None:
        local = []
        for _ in range(600):
            local.append(budget.consume())
        with results_lock:
            results.extend(local)

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactly 1000 True returns; the remaining 200 are False.
    assert results.count(True) == 1000
    assert results.count(False) == 200
    assert budget.remaining == 0


# ---------------------------------------------------------------------------
# _filter_registry
# ---------------------------------------------------------------------------


def test_filter_registry_none_returns_master_unchanged() -> None:
    master = ToolRegistry()
    master.register(_make_tool("a"))
    master.register(_make_tool("b"))
    filtered = _filter_registry(master, None)
    # Identity: unrestricted access returns the master itself.
    assert filtered is master


def test_filter_registry_with_subset_only_includes_listed_tools() -> None:
    master = ToolRegistry()
    master.register(_make_tool("a"))
    master.register(_make_tool("b"))
    master.register(_make_tool("c"))
    filtered = _filter_registry(master, ["a", "c"])
    assert filtered is not master
    assert "a" in filtered
    assert "b" not in filtered
    assert "c" in filtered
    assert len(filtered) == 2


def test_filter_registry_skips_unknown_names_silently() -> None:
    master = ToolRegistry()
    master.register(_make_tool("a"))
    filtered = _filter_registry(master, ["a", "ghost", "missing"])
    assert "a" in filtered
    assert "ghost" not in filtered
    assert len(filtered) == 1


def test_filter_registry_empty_list_returns_empty_registry() -> None:
    master = ToolRegistry()
    master.register(_make_tool("a"))
    filtered = _filter_registry(master, [])
    assert filtered is not master
    assert len(filtered) == 0


# ---------------------------------------------------------------------------
# make_delegate_tool integration tests
# ---------------------------------------------------------------------------


def _agent_result(text: str = "sub done") -> AgentResult:
    return AgentResult(
        text=text,
        tool_uses=[],
        provider="anthropic",
        model="claude-test",
        usage={},
    )


@pytest.fixture
def tmp_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "test.db")
    db.init()
    db.save_profile(
        AgentProfile(
            name="helper",
            system_prompt="You are a helper.",
            default_model="claude-helper-model",
            allowed_tools=None,
        )
    )
    return db


@pytest.fixture
def minimal_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(_make_tool("noop"))
    return registry


def test_delegate_tool_invokes_sub_agent(
    tmp_db: Database, minimal_registry: ToolRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def fake_run_agent_loop(prompt: str, **kwargs: Any) -> AgentResult:
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
        return _agent_result("done")

    monkeypatch.setattr("horus_os.agent.run_agent_loop", fake_run_agent_loop)

    budget = IterationBudget(5)
    tool = make_delegate_tool(
        db=tmp_db,
        master_registry=minimal_registry,
        parent_trace_id="parent-123",
        budget=budget,
        provider="anthropic",
    )
    assert tool.handler is not None
    out = tool.handler(agent_name="helper", task="do something")
    assert out == "done"
    assert captured["prompt"] == "do something"
    assert captured["kwargs"]["system_prompt"] == "You are a helper."
    assert captured["kwargs"]["provider"] == "anthropic"
    assert captured["kwargs"]["model"] == "claude-helper-model"
    assert captured["kwargs"]["budget"] is budget


def test_delegate_unknown_agent_returns_error_string(
    tmp_db: Database, minimal_registry: ToolRegistry
) -> None:
    tool = make_delegate_tool(
        db=tmp_db,
        master_registry=minimal_registry,
        parent_trace_id="p",
        budget=IterationBudget(5),
    )
    assert tool.handler is not None
    out = tool.handler(agent_name="ghost", task="anything")
    assert isinstance(out, str)
    assert "not found" in out.lower()
    assert "ghost" in out


def test_delegation_trace_linkage(
    tmp_db: Database, minimal_registry: ToolRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run_agent_loop(prompt: str, **kwargs: Any) -> AgentResult:
        return _agent_result("sub-result")

    monkeypatch.setattr("horus_os.agent.run_agent_loop", fake_run_agent_loop)

    # Persist a coordinator trace so the child has a real parent.
    parent_id = tmp_db.record_trace("coordinator prompt", _agent_result("coord"))
    tool = make_delegate_tool(
        db=tmp_db,
        master_registry=minimal_registry,
        parent_trace_id=parent_id,
        budget=IterationBudget(5),
    )
    assert tool.handler is not None
    tool.handler(agent_name="helper", task="child task")

    children = tmp_db.list_child_traces(parent_id)
    assert len(children) == 1
    assert children[0].parent_trace_id == parent_id
    assert children[0].agent_profile_name == "helper"
    assert children[0].prompt == "child task"
    assert children[0].response_text == "sub-result"
    assert children[0].latency_ms is not None


def test_subagent_tool_scoping(tmp_db: Database, monkeypatch: pytest.MonkeyPatch) -> None:
    # Reconfigure the helper profile to restrict to a single tool.
    tmp_db.save_profile(
        AgentProfile(
            name="helper",
            system_prompt="You are a helper.",
            allowed_tools=["noop"],
        )
    )
    master = ToolRegistry()
    master.register(_make_tool("noop"))
    master.register(_make_tool("secret_tool"))

    captured: dict[str, Any] = {}

    def fake_run_agent_loop(prompt: str, **kwargs: Any) -> AgentResult:
        captured["registry"] = kwargs["registry"]
        return _agent_result("ok")

    monkeypatch.setattr("horus_os.agent.run_agent_loop", fake_run_agent_loop)

    tool = make_delegate_tool(
        db=tmp_db,
        master_registry=master,
        parent_trace_id="p",
        budget=IterationBudget(5),
    )
    assert tool.handler is not None
    tool.handler(agent_name="helper", task="t")

    sub_registry = captured["registry"]
    assert "noop" in sub_registry
    assert "secret_tool" not in sub_registry


def test_budget_exhaustion_stops_tree() -> None:
    """A shared budget of zero refuses every consume() call."""
    budget = IterationBudget(0)
    assert budget.consume() is False
    # Even after multiple parallel attempts, the budget stays exhausted.
    assert budget.consume() is False


def test_parallel_delegation_runs_concurrently(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two delegate_to_agent calls in one batch both run and both return results."""
    calls: list[dict[str, Any]] = []
    calls_lock = threading.Lock()

    def fake_handler(*, agent_name: str, task: str) -> str:
        with calls_lock:
            calls.append({"agent_name": agent_name, "task": task})
        return f"{agent_name}:{task}"

    registry = ToolRegistry()
    registry.register(
        Tool(
            name="delegate_to_agent",
            description="delegate",
            parameters={"type": "object"},
            handler=fake_handler,
        )
    )
    uses = [
        ToolUse(id="tu_1", name="delegate_to_agent", input={"agent_name": "a", "task": "one"}),
        ToolUse(id="tu_2", name="delegate_to_agent", input={"agent_name": "b", "task": "two"}),
    ]
    result = AgentResult(
        text="",
        tool_uses=uses,
        provider="anthropic",
        model="claude-test",
        usage={},
    )
    outcomes = execute_tool_uses(registry, result)
    assert len(outcomes) == 2
    for out in outcomes:
        assert out.error is None
        assert out.name == "delegate_to_agent"
    # Both handlers actually ran; outputs may arrive in completion order.
    outputs = {o.output for o in outcomes}
    assert outputs == {"a:one", "b:two"}
    # tool_use_id matching is preserved.
    ids = {o.tool_use_id for o in outcomes}
    assert ids == {"tu_1", "tu_2"}
    assert len(calls) == 2


def test_parallel_delegation_mixed_with_other_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-delegate tools stay sequential while parallel delegates run alongside."""
    registry = ToolRegistry()
    registry.register(_make_tool("noop"))
    registry.register(
        Tool(
            name="delegate_to_agent",
            description="d",
            parameters={"type": "object"},
            handler=lambda **kwargs: f"sub:{kwargs.get('task', '')}",
        )
    )
    uses = [
        ToolUse(id="tu_seq", name="noop", input={}),
        ToolUse(id="tu_d1", name="delegate_to_agent", input={"agent_name": "a", "task": "x"}),
        ToolUse(id="tu_d2", name="delegate_to_agent", input={"agent_name": "b", "task": "y"}),
    ]
    result = AgentResult(
        text="",
        tool_uses=uses,
        provider="anthropic",
        model="claude-test",
        usage={},
    )
    outcomes = execute_tool_uses(registry, result)
    assert len(outcomes) == 3
    by_id = {o.tool_use_id: o for o in outcomes}
    assert by_id["tu_seq"].output == "noop"
    assert by_id["tu_d1"].output == "sub:x"
    assert by_id["tu_d2"].output == "sub:y"


def test_module_reexports_make_delegate_tool() -> None:
    """make_delegate_tool is accessible from the delegation module surface."""
    assert hasattr(delegation_module, "make_delegate_tool")
    assert callable(delegation_module.make_delegate_tool)
