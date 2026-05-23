"""Delegation primitives for multi-agent orchestration.

This module hosts the shared `IterationBudget` (a lock-protected counter
that spans a whole delegation tree) and the `_filter_registry` helper that
narrows a master `ToolRegistry` to a sub-agent's `allowed_tools`.

The `make_delegate_tool` factory (which wires the `delegate_to_agent`
tool into the runtime) is added in Plan 13-02.
"""

from __future__ import annotations

import threading

from horus_os.tools.registry import ToolRegistry


class IterationBudget:
    """Thread-safe iteration counter shared across a delegation tree.

    A single `IterationBudget` instance is created at the top-level
    `run_agent_loop` call and passed by reference through every sub-agent
    invocation. `consume()` decrements the counter under a lock; when the
    pool is exhausted it returns False and the loop exits.
    """

    def __init__(self, max_iterations: int) -> None:
        self._remaining = max_iterations
        self._lock = threading.Lock()

    def consume(self) -> bool:
        """Decrement the budget by one. Returns False when no budget remains."""
        with self._lock:
            if self._remaining <= 0:
                return False
            self._remaining -= 1
            return True

    @property
    def remaining(self) -> int:
        """The current budget remaining. Snapshot read under the lock."""
        with self._lock:
            return self._remaining


def _filter_registry(
    master: ToolRegistry,
    allowed_tools: list[str] | None,
) -> ToolRegistry:
    """Return a `ToolRegistry` restricted to `allowed_tools`.

    When `allowed_tools` is None the master registry is returned
    unchanged (unrestricted access). Unknown names in `allowed_tools`
    are skipped silently, matching the behavior we want for optional
    sub-agent capabilities.

    Note: when `allowed_tools` is None and the master registry contains
    `delegate_to_agent`, sub-agents inherit delegation capability. This
    is intentional for v0.2; the shared `IterationBudget` is the safety
    valve against runaway recursion.
    """
    if allowed_tools is None:
        return master
    filtered = ToolRegistry()
    for name in allowed_tools:
        tool = master.get(name)
        if tool is not None:
            filtered.register(tool)
    return filtered
