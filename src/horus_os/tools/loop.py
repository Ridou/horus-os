"""Tool execution helpers.

`execute_tool_uses` walks an `AgentResult.tool_uses` list, invokes each
through a `ToolRegistry`, and returns a `ToolResult` for each. The
multi-turn model loop (send tool_results back, re-prompt the model)
lives in higher-level surfaces (CLI, dashboard) that own conversation
state.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from horus_os.tools.registry import ToolRegistry
from horus_os.types import AgentResult, ToolResult


def execute_tool_uses(
    registry: ToolRegistry,
    result: AgentResult,
    *,
    on_log: Callable[[ToolResult], None] | None = None,
) -> list[ToolResult]:
    """Invoke every tool_use in `result` and return one `ToolResult` per use.

    Exceptions raised by individual handlers are captured in
    `ToolResult.error`; execution continues to the next tool_use.
    """
    outcomes: list[ToolResult] = []
    for use in result.tool_uses:
        start = time.perf_counter()
        outcome = ToolResult(tool_use_id=use.id, name=use.name)
        try:
            outcome.output = registry.invoke(use.name, use.input)
        except BaseException as exc:
            outcome.error = f"{type(exc).__name__}: {exc}"
        outcome.latency_ms = int((time.perf_counter() - start) * 1000)
        outcomes.append(outcome)
        if on_log is not None:
            _call_logger(on_log, outcome)
    return outcomes


def _call_logger(on_log: Callable[[ToolResult], Any], outcome: ToolResult) -> None:
    try:
        on_log(outcome)
    except BaseException:
        pass
