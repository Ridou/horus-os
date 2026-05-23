"""Tests for delegation primitives: IterationBudget and _filter_registry.

Plan 13-02 will add make_delegate_tool integration tests to this file.
"""

from __future__ import annotations

import threading

from horus_os.tools.delegation import IterationBudget, _filter_registry
from horus_os.tools.registry import ToolRegistry
from horus_os.types import Tool


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
