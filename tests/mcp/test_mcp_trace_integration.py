"""End-to-end proof an MCP tool call is traced like a builtin (MCP-01).

Because an MCP tool is registered as an ordinary `Tool` in the shared
`ToolRegistry`, `execute_tool_uses` publishes one `tool_invocations`-shaped
`ObsToolCallEvent` for each MCP call with NO new schema, exactly as it does for
a builtin. This test registers a fake MCP tool via a real `MCPRegistry` (no
subprocess), runs it through `execute_tool_uses` with a trace_id, and asserts
the published event carries the `mcp:{server}:{tool}` name and status
"success" -- the same event shape a builtin tool produces.

The MCP server boundary is faked in-process via the registry's client_factory;
the observability boundary is the real singleton ObservationBus, reset and
subscribed exactly as tests/observability/test_tool_loop_capture.py does.
"""

from __future__ import annotations

from horus_os.mcp_client.client import DiscoveredTool
from horus_os.mcp_client.config import MCPServerConfig
from horus_os.mcp_client.registry import MCPRegistry
from horus_os.observability import (
    get_observation_bus,
    reset_observation_bus_for_tests,
)
from horus_os.observability.bus import ObservationEvent
from horus_os.observability.bus import ToolCallEvent as ObsToolCallEvent
from horus_os.tools.loop import execute_tool_uses
from horus_os.tools.registry import ToolRegistry
from horus_os.types import AgentResult, ToolUse
from tests.mcp.conftest import make_factory


def _collect() -> list[ObservationEvent]:
    events: list[ObservationEvent] = []
    reset_observation_bus_for_tests()
    get_observation_bus().subscribe(events.append)
    return events


def test_mcp_tool_call_writes_trace_row() -> None:
    """An MCP tool call publishes one tool_invocations-shaped success event.

    The event's tool_name is the namespaced mcp:web:search name and its status
    is "success", matching the shape a builtin tool call produces (MCP-01: an
    MCP call cannot bypass tracing because it is an ordinary ToolRegistry
    entry).
    """
    events = _collect()

    registry = ToolRegistry()
    server = MCPServerConfig(name="web", transport="streamable-http", url="http://x/mcp")
    tools = {"web": [DiscoveredTool(name="search", description="Search the web", input_schema={})]}
    factory = make_factory(tools)
    mcp_registry = MCPRegistry([server], registry, client_factory=factory)

    import asyncio

    asyncio.run(mcp_registry.start())
    assert registry.get("mcp:web:search") is not None

    # Drive the namespaced tool through the SAME execute_tool_uses path the
    # agent loop uses, with a run-level trace_id.
    result = AgentResult(
        text="",
        tool_uses=[ToolUse(id="u1", name="mcp:web:search", input={"query": "horus"})],
        provider="stub",
        model="stub",
    )
    outcomes = execute_tool_uses(registry, result, trace_id="trace-mcp-1")

    # The tool ran and returned the fake client's string result.
    assert len(outcomes) == 1
    assert outcomes[0].output == "fake-result"
    assert outcomes[0].error is None

    tool_events = [e for e in events if isinstance(e, ObsToolCallEvent)]
    assert len(tool_events) == 1
    event = tool_events[0]
    assert event.trace_id == "trace-mcp-1"
    assert event.tool_name == "mcp:web:search"
    assert event.status == "success"
    assert event.error_type is None
    assert event.error_message is None
    # retry_count is None by design, identical to a builtin tool event.
    assert event.retry_count is None

    # The handler bridged the call into the fake client with the BARE tool
    # name (the MCP server expects its own name, not the mcp: prefix).
    fake = factory.built[0]
    assert fake.calls == [("search", {"query": "horus"})]


def test_mcp_tool_event_matches_builtin_event_shape() -> None:
    """The MCP event carries the same fields a builtin tool event does.

    Runs a builtin and an MCP tool through the same execute_tool_uses path and
    asserts the two published events share the same field surface (kind,
    status, the trace fields), differing only in the tool_name value. This pins
    MCP-01's "identical in shape to a builtin tool call" requirement.
    """
    events = _collect()

    from horus_os.types import Tool

    registry = ToolRegistry()
    registry.register(
        Tool(
            name="builtin_echo",
            description="echo",
            parameters={"type": "object", "properties": {}},
            handler=lambda **kw: "echoed",
        )
    )
    server = MCPServerConfig(name="web", transport="streamable-http", url="http://x/mcp")
    factory = make_factory(
        {"web": [DiscoveredTool(name="search", description="search", input_schema={})]}
    )
    mcp_registry = MCPRegistry([server], registry, client_factory=factory)

    import asyncio

    asyncio.run(mcp_registry.start())

    result = AgentResult(
        text="",
        tool_uses=[
            ToolUse(id="b1", name="builtin_echo", input={}),
            ToolUse(id="m1", name="mcp:web:search", input={"q": "x"}),
        ],
        provider="stub",
        model="stub",
    )
    execute_tool_uses(registry, result, trace_id="shape-trace")

    tool_events = [e for e in events if isinstance(e, ObsToolCallEvent)]
    assert len(tool_events) == 2
    by_name = {e.tool_name: e for e in tool_events}
    builtin_event = by_name["builtin_echo"]
    mcp_event = by_name["mcp:web:search"]

    # Same field surface: every dataclass field present on one is present on
    # the other, and the non-name fields match.
    builtin_fields = set(vars(builtin_event).keys())
    mcp_fields = set(vars(mcp_event).keys())
    assert builtin_fields == mcp_fields
    assert builtin_event.kind == mcp_event.kind == "TOOL_CALL"
    assert builtin_event.status == mcp_event.status == "success"
    assert builtin_event.trace_id == mcp_event.trace_id == "shape-trace"
    assert builtin_event.error_type == mcp_event.error_type is None
