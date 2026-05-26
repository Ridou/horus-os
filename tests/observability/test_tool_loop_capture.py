"""Phase 33 Task 3 tests: tools/loop.py:_execute_one publishes ObsToolCallEvent.

Pin down the Pitfall 9 substrate contract: status enum, retry_count NULL,
error_message as class name only (never user-supplied content), and the
trace_id threading from execute_tool_uses through every code path
(sequential, single-delegate, parallel-delegate).
"""

from __future__ import annotations

from horus_os.observability import (
    get_observation_bus,
    reset_observation_bus_for_tests,
)
from horus_os.observability.bus import (
    ObservationEvent,
)
from horus_os.observability.bus import (
    ToolCallEvent as ObsToolCallEvent,
)
from horus_os.tools.loop import _execute_one, execute_tool_uses
from horus_os.tools.registry import ToolRegistry
from horus_os.types import AgentResult, Tool, ToolUse


def _collect():
    events: list[ObservationEvent] = []
    reset_observation_bus_for_tests()
    get_observation_bus().subscribe(events.append)
    return events


def _noop_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="noop",
            description="No-op tool for tool-loop capture tests.",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "ok",
        )
    )
    return registry


def test_successful_tool_publishes_event_with_status_success() -> None:
    events = _collect()
    registry = _noop_registry()
    _execute_one(registry, ToolUse(id="x", name="noop", input={}), trace_id="abc123")
    tool_events = [e for e in events if isinstance(e, ObsToolCallEvent)]
    assert len(tool_events) == 1
    e = tool_events[0]
    assert e.trace_id == "abc123"
    assert e.tool_name == "noop"
    assert e.status == "success"
    assert e.error_type is None
    assert e.error_message is None
    assert e.retry_count is None
    assert e.output_size == 2  # len(b"ok")


def test_failing_tool_publishes_event_with_class_name_only() -> None:
    events = _collect()
    registry = ToolRegistry()
    user_secret = "/Users/santino/secret/path/credentials.json leaked"

    def _leaky(**_kwargs):
        raise ValueError(user_secret)

    registry.register(
        Tool(
            name="leaky",
            description="A tool that leaks user-supplied content in its exception.",
            parameters={"type": "object", "properties": {}},
            handler=_leaky,
        )
    )
    _execute_one(registry, ToolUse(id="x", name="leaky", input={}), trace_id="t-leak")

    tool_events = [e for e in events if isinstance(e, ObsToolCallEvent)]
    assert len(tool_events) == 1
    e = tool_events[0]
    assert e.status == "error"
    assert e.error_type == "ValueError"
    # error_message holds the CLASS NAME, never the message body.
    assert e.error_message == "ValueError"
    # Belt-and-braces: the leaked user-supplied content must not appear
    # in any of the event fields the persister writes.
    sweep = " ".join(
        str(v)
        for v in (
            e.trace_id,
            e.tool_name,
            e.invocation_id,
            e.status,
            e.error_type,
            e.error_message,
            e.retry_count,
            e.output_size,
        )
    )
    assert "/Users/santino/secret/path" not in sweep
    assert "credentials.json" not in sweep


def test_omitted_trace_id_publishes_nothing() -> None:
    events = _collect()
    registry = _noop_registry()
    _execute_one(registry, ToolUse(id="x", name="noop", input={}))
    tool_events = [e for e in events if isinstance(e, ObsToolCallEvent)]
    assert tool_events == []


def test_execute_tool_uses_threads_trace_id_into_all_paths() -> None:
    events = _collect()
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="noop",
            description="Sequential tool.",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "ok",
        )
    )
    # delegate_to_agent fanout: register a fake handler so multiple
    # delegate uses exercise the ThreadPoolExecutor branch.
    registry.register(
        Tool(
            name="delegate_to_agent",
            description="Fake delegate for capture tests.",
            parameters={"type": "object", "properties": {}},
            handler=lambda **_: "delegated",
        )
    )
    result = AgentResult(
        text="",
        tool_uses=[
            ToolUse(id="u1", name="noop", input={}),
            ToolUse(id="u2", name="delegate_to_agent", input={}),
            ToolUse(id="u3", name="delegate_to_agent", input={}),
        ],
        provider="stub",
        model="stub",
    )
    execute_tool_uses(registry, result, trace_id="zzz")
    tool_events = [e for e in events if isinstance(e, ObsToolCallEvent)]
    assert len(tool_events) == 3
    for e in tool_events:
        assert e.trace_id == "zzz"
        assert e.status == "success"
        assert e.latency_ms >= 0
