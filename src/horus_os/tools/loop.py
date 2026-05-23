"""Tool execution helpers.

`execute_tool_uses` walks an `AgentResult.tool_uses` list, invokes each
through a `ToolRegistry`, and returns a `ToolResult` for each. Multiple
`delegate_to_agent` calls in one batch run concurrently through a
`ThreadPoolExecutor` so a coordinator can fan work out to several
sub-agents in one turn; non-delegate tools and lone delegate calls
stay on the sync path.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from horus_os.tools.registry import ToolRegistry
from horus_os.types import AgentResult, ToolResult, ToolUse

DELEGATE_TOOL_NAME = "delegate_to_agent"


def execute_tool_uses(
    registry: ToolRegistry,
    result: AgentResult,
    *,
    on_log: Callable[[ToolResult], None] | None = None,
) -> list[ToolResult]:
    """Invoke every tool_use in `result` and return one `ToolResult` per use.

    Non-delegate tools run sequentially in the order they appear.
    Multiple `delegate_to_agent` calls in the same batch run in
    parallel through a `ThreadPoolExecutor`; their `ToolResult` outputs
    are appended in completion order (the model matches results to
    requests by `tool_use_id`, not list position).

    Exceptions raised by individual handlers are captured in
    `ToolResult.error`; execution continues to the next tool_use.
    """
    delegate_uses: list[ToolUse] = []
    other_uses: list[ToolUse] = []
    for use in result.tool_uses:
        if use.name == DELEGATE_TOOL_NAME:
            delegate_uses.append(use)
        else:
            other_uses.append(use)

    outcomes: list[ToolResult] = []

    # Non-delegate tools keep the original sequential semantics.
    for use in other_uses:
        outcome = _execute_one(registry, use)
        outcomes.append(outcome)
        if on_log is not None:
            _call_logger(on_log, outcome)

    # Delegate tools: parallel when there are 2 or more, sequential when 1.
    if len(delegate_uses) == 1:
        outcome = _execute_one(registry, delegate_uses[0])
        outcomes.append(outcome)
        if on_log is not None:
            _call_logger(on_log, outcome)
    elif len(delegate_uses) > 1:
        with ThreadPoolExecutor(max_workers=len(delegate_uses)) as pool:
            futures = [pool.submit(_execute_one, registry, u) for u in delegate_uses]
            for future in as_completed(futures):
                outcome = future.result()
                outcomes.append(outcome)
                if on_log is not None:
                    _call_logger(on_log, outcome)

    return outcomes


def _execute_one(registry: ToolRegistry, use: ToolUse) -> ToolResult:
    """Run one tool use against `registry` and capture its outcome."""
    start = time.perf_counter()
    outcome = ToolResult(tool_use_id=use.id, name=use.name)
    try:
        outcome.output = registry.invoke(use.name, use.input)
    except BaseException as exc:
        outcome.error = f"{type(exc).__name__}: {exc}"
    outcome.latency_ms = int((time.perf_counter() - start) * 1000)
    return outcome


def _call_logger(on_log: Callable[[ToolResult], Any], outcome: ToolResult) -> None:
    try:
        on_log(outcome)
    except BaseException:
        pass
