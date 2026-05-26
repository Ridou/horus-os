"""In-process synchronous observation bus.

Subscribers fire in subscribe order: CostAnnotator first (Phase 34),
SQLitePersister second, OtelExporter last (Phase 38). Subscriber
exceptions are swallowed to match tools/loop.py:_call_logger semantics;
a slow OTel exporter or a crashed persister must never break the agent
loop.

This module defines the on-the-wire shape of an observation:

- LLMCallEvent for one provider call (one row in llm_calls)
- ToolCallEvent for one tool invocation (one row in tool_invocations)
- RunEndEvent for the end of an agent run (rollup into traces)

Phase 32 ships the bus, the events, and the SQLitePersister. Phase 33
wires capture sites in agent.py and tools/loop.py. No runner code is
touched in this phase.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal


def _now_iso() -> str:
    """Return an ISO-8601 UTC timestamp with a trailing Z suffix."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _new_id() -> str:
    """Return a fresh 32-char UUID4 hex identifier."""
    return uuid.uuid4().hex


@dataclass(kw_only=True)
class ObservationEvent:
    """Base observation event. Concrete subclasses set `kind` and add fields.

    `trace_id` is the agent-run scope (one trace per top-level run, shared by
    all child LLM calls and tool invocations within that run). `created_at`
    is the ISO-8601 UTC timestamp captured at construction.
    """

    kind: Literal["LLM_CALL", "TOOL_CALL", "RUN_END"]
    trace_id: str
    created_at: str = field(default_factory=_now_iso)


@dataclass(kw_only=True)
class LLMCallEvent(ObservationEvent):
    """One provider call. Persists to llm_calls.

    `latency_ms`: Wall-clock elapsed milliseconds from operation start to the
    moment the result is available to the caller, measured via
    time.perf_counter(). Inclusive of SDK-level retries, backoff, queueing,
    and stream drain where applicable. NEVER use time.time() for this field;
    see scripts/lint_no_wallclock.py.

    `cost_usd` is None until Phase 34's CostAnnotator subscriber populates
    it before SQLitePersister sees the event. `pricing_missing` flips True
    when the bundled pricing table has no row for (provider, model).
    """

    kind: Literal["LLM_CALL", "TOOL_CALL", "RUN_END"] = "LLM_CALL"
    iteration_idx: int
    provider: str
    model: str
    call_id: str = field(default_factory=_new_id)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cost_usd: float | None = None
    pricing_missing: bool = False
    latency_ms: int = 0
    status: str = "success"
    error_message: str | None = None
    error_type: str | None = None


@dataclass(kw_only=True)
class ToolCallEvent(ObservationEvent):
    """One tool invocation. Persists to tool_invocations.

    `latency_ms`: Wall-clock elapsed milliseconds from operation start to the
    moment the result is available to the caller, measured via
    time.perf_counter(). Inclusive of SDK-level retries, backoff, queueing,
    and stream drain where applicable. NEVER use time.time() for this field;
    see scripts/lint_no_wallclock.py.

    `retry_count` is best-effort and may be NULL when the SDK does not
    expose a per-call retry counter (PITFALLS.md Pitfall 9).

    Note: this class is distinct from `horus_os.types.ToolCallEvent`, which
    is the streaming-surface notification surfaced by `run_agent_stream`.
    The two types live in different modules and represent different
    concerns; callers disambiguate by module path.
    """

    kind: Literal["LLM_CALL", "TOOL_CALL", "RUN_END"] = "TOOL_CALL"
    tool_name: str
    invocation_id: str = field(default_factory=_new_id)
    parent_trace_id: str | None = None
    latency_ms: int = 0
    status: str = "success"
    error_message: str | None = None
    error_type: str | None = None
    retry_count: int | None = None
    output_size: int | None = None


@dataclass(kw_only=True)
class RunEndEvent(ObservationEvent):
    """End of an agent run. SQLitePersister rolls up llm_calls into traces.

    `latency_ms`: Wall-clock elapsed milliseconds from operation start to the
    moment the result is available to the caller, measured via
    time.perf_counter(). Inclusive of SDK-level retries, backoff, queueing,
    and stream drain where applicable. NEVER use time.time() for this field;
    see scripts/lint_no_wallclock.py.

    Writes into traces.total_duration_ms via SQLitePersister.
    """

    kind: Literal["LLM_CALL", "TOOL_CALL", "RUN_END"] = "RUN_END"
    latency_ms: int = 0


class ObservationBus:
    """Synchronous in-process pub-sub for ObservationEvent values.

    Subscribers receive every event in the order they subscribed.
    A subscriber that raises does not block siblings: each handler call is
    guarded with `try/except BaseException: pass` to mirror the
    fire-and-forget semantics of `tools/loop.py:_call_logger`. A slow
    or broken Phase 38 OTel exporter must never break the Phase 33
    runner.
    """

    def __init__(self) -> None:
        self._subscribers: list[Callable[[ObservationEvent], None]] = []

    def subscribe(self, handler: Callable[[ObservationEvent], None]) -> Callable[[], None]:
        """Register a handler. Returns an unsubscribe callable.

        Calling the returned function removes the handler from the
        subscriber list. The unsubscribe is idempotent: calling it twice
        is a no-op the second time.
        """
        self._subscribers.append(handler)

        def _unsubscribe() -> None:
            try:
                self._subscribers.remove(handler)
            except ValueError:
                pass

        return _unsubscribe

    def publish(self, event: ObservationEvent) -> None:
        """Dispatch `event` to every subscriber in subscribe order.

        Each handler call is wrapped in try/except BaseException so one
        broken subscriber cannot starve the rest. This matches the
        exception-swallow contract of tools/loop.py:_call_logger.
        """
        for handler in list(self._subscribers):
            try:
                handler(event)
            except BaseException:
                pass


__all__ = [
    "LLMCallEvent",
    "ObservationBus",
    "ObservationEvent",
    "RunEndEvent",
    "ToolCallEvent",
]
