"""Tool execution helpers.

`execute_tool_uses` walks an `AgentResult.tool_uses` list, invokes each
through a `ToolRegistry`, and returns a `ToolResult` for each. Multiple
`delegate_to_agent` calls in one batch run concurrently through a
`ThreadPoolExecutor` so a coordinator can fan work out to several
sub-agents in one turn; non-delegate tools and lone delegate calls
stay on the sync path.

Phase 33 adds observability capture: when callers pass a `trace_id`,
each `_execute_one` invocation publishes one `ObsToolCallEvent` to the
singleton ObservationBus. The alias avoids collision with
`horus_os.types.ToolCallEvent` which is the streaming-surface event.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from horus_os.observability import get_observation_bus

# Alias to disambiguate from horus_os.types.ToolCallEvent (streaming
# surface). The observability ToolCallEvent persists into
# tool_invocations; the types one notifies SSE consumers.
from horus_os.observability.bus import ToolCallEvent as ObsToolCallEvent
from horus_os.tools.registry import ToolRegistry
from horus_os.types import AgentResult, ToolResult, ToolUse

DELEGATE_TOOL_NAME = "delegate_to_agent"


def execute_tool_uses(
    registry: ToolRegistry,
    result: AgentResult,
    *,
    on_log: Callable[[ToolResult], None] | None = None,
    trace_id: str | None = None,
) -> list[ToolResult]:
    """Invoke every tool_use in `result` and return one `ToolResult` per use.

    Non-delegate tools run sequentially in the order they appear.
    Multiple `delegate_to_agent` calls in the same batch run in
    parallel through a `ThreadPoolExecutor`; their `ToolResult` outputs
    are appended in completion order (the model matches results to
    requests by `tool_use_id`, not list position).

    Exceptions raised by individual handlers are captured in
    `ToolResult.error`; execution continues to the next tool_use.

    `trace_id` (Phase 33) is threaded into every `_execute_one` call so
    each tool invocation publishes an `ObsToolCallEvent` carrying the
    same run-level trace_id as the surrounding LLMCallEvents. When None,
    no observability event is published (back-compat for direct callers
    like unit tests and scripts).
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
        outcome = _execute_one(registry, use, trace_id=trace_id)
        outcomes.append(outcome)
        if on_log is not None:
            _call_logger(on_log, outcome)

    # Delegate tools: parallel when there are 2 or more, sequential when 1.
    if len(delegate_uses) == 1:
        outcome = _execute_one(registry, delegate_uses[0], trace_id=trace_id)
        outcomes.append(outcome)
        if on_log is not None:
            _call_logger(on_log, outcome)
    elif len(delegate_uses) > 1:
        with ThreadPoolExecutor(max_workers=len(delegate_uses)) as pool:
            futures = [
                pool.submit(_execute_one, registry, u, trace_id=trace_id) for u in delegate_uses
            ]
            for future in as_completed(futures):
                outcome = future.result()
                outcomes.append(outcome)
                if on_log is not None:
                    _call_logger(on_log, outcome)

    return outcomes


def _execute_one(
    registry: ToolRegistry,
    use: ToolUse,
    *,
    trace_id: str | None = None,
) -> ToolResult:
    """Run one tool use against `registry` and capture its outcome.

    When `trace_id` is provided, publishes an `ObsToolCallEvent` to the
    singleton ObservationBus AFTER the timing block. The event carries
    only the exception CLASS NAME in `error_type` and `error_message`,
    never the message body, because `str(exc)` may contain user-supplied
    paths or content (PITFALLS.md Pitfall 9 + threat T-33-01).
    """
    start = time.perf_counter()
    outcome = ToolResult(tool_use_id=use.id, name=use.name)
    try:
        outcome.output = registry.invoke(use.name, use.input)
    except BaseException as exc:
        outcome.error = f"{type(exc).__name__}: {exc}"
    outcome.latency_ms = int((time.perf_counter() - start) * 1000)

    # gated on trace_id so direct callers (unit tests, scripts) without
    # an observability context do not publish phantom events.
    if trace_id is not None:
        _status = "success" if outcome.error is None else "error"
        # outcome.error is formatted as "{ClassName}: {message}" by the
        # try/except above. Split on the FIRST colon to recover the
        # class name only; never persist the message body (Pitfall 9).
        _error_class = (
            outcome.error.split(":", 1)[0] if outcome.error is not None else None
        )
        _output_size = (
            len(str(outcome.output).encode("utf-8")) if outcome.output is not None else 0
        )
        get_observation_bus().publish(
            ObsToolCallEvent(
                trace_id=trace_id,
                tool_name=use.name,
                latency_ms=max(0, outcome.latency_ms or 0),
                status=_status,
                error_type=_error_class,
                error_message=_error_class,
                # retry_count is None by design: the Anthropic SDK does not
                # surface per-call retry counts without monkey-patching the
                # transport layer (PITFALLS.md Pitfall 9). A Phase 38 OTel
                # subscriber can fill this from spans if a user wires it.
                retry_count=None,
                output_size=_output_size,
            )
        )
    return outcome


def _call_logger(on_log: Callable[[ToolResult], Any], outcome: ToolResult) -> None:
    try:
        on_log(outcome)
    except BaseException:
        pass
