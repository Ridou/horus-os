"""Delegation primitives for multi-agent orchestration.

This module hosts the shared `IterationBudget` (a lock-protected counter
that spans a whole delegation tree), the `_filter_registry` helper that
narrows a master `ToolRegistry` to a sub-agent's `allowed_tools`, and
the `make_delegate_tool` factory that produces a `delegate_to_agent`
tool bound to a database, a master registry, a parent trace, and a
shared budget.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from horus_os.tools.registry import ToolRegistry
from horus_os.types import Tool

if TYPE_CHECKING:
    from horus_os.storage import Database


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


def make_delegate_tool(
    *,
    db: Database,
    master_registry: ToolRegistry,
    parent_trace_id: str,
    budget: IterationBudget,
    provider: str = "anthropic",
) -> Tool:
    """Build a `delegate_to_agent` Tool bound to a delegation context.

    The returned tool's handler:
      1. Looks up the named sub-agent profile in `db`.
      2. Returns an error string if the profile is missing (consistent
         with `execute_tool_uses` exception capture).
      3. Filters `master_registry` to the profile's `allowed_tools`.
      4. Calls `run_agent_loop` with the shared `budget` and the
         profile's `system_prompt`.
      5. Records the sub-agent trace with `parent_trace_id` and the
         profile name so the dashboard can reconstruct the tree.
      6. Returns the sub-agent's final text response.

    The closure captures `db`, `master_registry`, `parent_trace_id`,
    `budget`, and `provider` so the tool input itself stays a simple
    JSON payload of `agent_name` and `task` strings.
    """
    # Local imports break the agent <-> delegation import cycle at module
    # load time. agent.run_agent_loop imports IterationBudget from this
    # module, so we defer the reverse direction to call time.
    from horus_os.agent import run_agent_loop

    def _delegate(agent_name: str, task: str) -> str:
        profile = db.load_profile(agent_name)
        if profile is None:
            return f"Error: agent profile {agent_name!r} not found"
        sub_registry = _filter_registry(master_registry, profile.allowed_tools)
        start = time.perf_counter()
        result = run_agent_loop(
            task,
            registry=sub_registry,
            provider=provider,
            model=profile.default_model,
            budget=budget,
            system_prompt=profile.system_prompt,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        db.record_trace(
            task,
            result,
            parent_trace_id=parent_trace_id,
            agent_profile_name=profile.name,
            latency_ms=latency_ms,
        )
        return result.text

    return Tool(
        name="delegate_to_agent",
        description=(
            "Delegate a subtask to a named sub-agent. Returns the sub-agent's final text response."
        ),
        parameters={
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Name of the agent profile to delegate to.",
                },
                "task": {
                    "type": "string",
                    "description": "The task or question to send to the sub-agent.",
                },
            },
            "required": ["agent_name", "task"],
        },
        handler=_delegate,
    )
