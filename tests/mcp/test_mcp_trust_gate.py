"""Opt-in trust gate and teardown unit tests (Pitfalls MC-1/MCP-03, MC-3/MCP-04).

Pins the BLOCKING trust gate (an empty or absent config registers ZERO
tools), the explicit cross-OS subprocess teardown call sequence on a fake
process, that a collision surfaces via `errors()` without shadowing a
builtin, and that `stop()` tears every client down.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from horus_os.mcp_client.client import (
    MCP_TERMINATE_TIMEOUT_S,
    DiscoveredTool,
    MCPClient,
    _ProcessHandle,
)
from horus_os.mcp_client.config import MCPServerConfig
from horus_os.mcp_client.registry import MCPRegistry
from horus_os.tools.registry import ToolRegistry
from horus_os.types import Tool
from tests.mcp.conftest import FakeProcess, make_factory


def _builtin(name: str) -> Tool:
    return Tool(name=name, description="builtin", parameters={}, handler=lambda **kw: "b")


def test_absent_config_file_yields_empty_server_list(tmp_path: Path) -> None:
    # MCP-03 trust gate: a path that does not exist returns [] (no servers,
    # no network probe).
    missing = tmp_path / "does-not-exist" / "mcp.toml"
    assert MCPServerConfig.load(missing) == []

    # A file with no [[mcp.servers]] array also returns [].
    empty = tmp_path / "mcp.toml"
    empty.write_text("[other]\nkey = 1\n", encoding="utf-8")
    assert MCPServerConfig.load(empty) == []


@pytest.mark.asyncio
async def test_unconfigured_server_registers_no_tools() -> None:
    # MCP-03: an MCPRegistry built from [] registers zero tools; after start()
    # the passed ToolRegistry length is unchanged.
    registry = ToolRegistry()
    registry.register(_builtin("read_file"))
    before = len(registry)

    factory = make_factory({})
    mcp_registry = MCPRegistry([], registry, client_factory=factory)
    await mcp_registry.start()

    assert len(registry) == before
    # The empty fast path never even builds a client.
    assert factory.built == []


def test_stop_terminates_and_waits() -> None:
    # MC-3: stop() drives terminate() then wait(); when the process is still
    # running past the bound it escalates to kill(). Idempotent on a second
    # call. A no-such-process race is swallowed.
    config = MCPServerConfig(name="fs", transport="stdio", command=["true"])
    client = MCPClient(config)

    # Inject a fake process that does NOT exit on terminate, forcing the
    # kill() escalation.
    fake = FakeProcess(exit_on_terminate=False)
    client._process = fake  # type: ignore[assignment]

    client.stop()
    assert fake.calls == ["terminate", "wait", "kill"]

    # Idempotent: a second stop() is a no-op and records nothing new.
    client.stop()
    assert fake.calls == ["terminate", "wait", "kill"]


def test_stop_skips_kill_when_process_exits() -> None:
    # When wait() reports the process exited, kill() is NOT called.
    config = MCPServerConfig(name="fs", transport="stdio", command=["true"])
    client = MCPClient(config)
    fake = FakeProcess(exit_on_terminate=True)
    client._process = fake  # type: ignore[assignment]

    client.stop()
    assert fake.calls == ["terminate", "wait"]
    assert "kill" not in fake.calls


def test_stop_swallows_no_such_process_race() -> None:
    # A process whose terminate()/wait()/kill() raise (already-exited race)
    # must not propagate out of stop().
    class RaisingProcess:
        def terminate(self) -> None:
            raise ProcessLookupError("no such process")

        def wait(self, timeout: float) -> bool:
            raise ProcessLookupError("no such process")

        def kill(self) -> None:
            raise ProcessLookupError("no such process")

        def is_running(self) -> bool:
            return True

    config = MCPServerConfig(name="fs", transport="stdio", command=["true"])
    client = MCPClient(config)
    client._process = RaisingProcess()  # type: ignore[assignment]

    # Must not raise.
    client.stop()


def test_process_handle_timeout_constant_is_bounded() -> None:
    # The teardown bound is a small, finite number of seconds (MC-3).
    assert 0 < MCP_TERMINATE_TIMEOUT_S <= 30
    assert _ProcessHandle is not None


@pytest.mark.asyncio
async def test_collision_surfaces_via_errors_without_shadowing() -> None:
    # MC-4: when a server's tool, after prefixing, would land on a name that
    # is already a reserved builtin, start() records the CollisionError in
    # errors() (it is NOT swallowed) and does NOT overwrite the existing
    # entry. We pre-register a builtin occupying the exact namespaced slot
    # the MCP tool would produce so the surfacing path is exercised.
    registry = ToolRegistry()
    occupied = Tool(
        name="mcp:evil:read_file",
        description="reserved-builtin",
        parameters={},
        handler=lambda **kw: "reserved",
    )
    registry.register(occupied)

    server = MCPServerConfig(name="evil", transport="streamable-http", url="http://x/mcp")
    tools = {"evil": [DiscoveredTool(name="read_file", description="hostile", input_schema={})]}
    factory = make_factory(tools)
    mcp_registry = MCPRegistry([server], registry, client_factory=factory)

    await mcp_registry.start()

    # CollisionError surfaced, not swallowed.
    assert "evil" in mcp_registry.errors()
    assert "mcp:evil:read_file" in mcp_registry.errors()["evil"]
    # The pre-existing entry is untouched (no shadowing/overwrite).
    assert registry.get("mcp:evil:read_file").description == "reserved-builtin"
    # The offending client was torn down.
    assert factory.built[0].stopped is True


@pytest.mark.asyncio
async def test_stop_tears_down_all_clients() -> None:
    # MCP-04: MCPRegistry.stop() calls stop() on every started client.
    registry = ToolRegistry()
    servers = [
        MCPServerConfig(name="a", transport="streamable-http", url="http://a/mcp"),
        MCPServerConfig(name="b", transport="streamable-http", url="http://b/mcp"),
    ]
    tools = {
        "a": [DiscoveredTool(name="ta", description="ta", input_schema={})],
        "b": [DiscoveredTool(name="tb", description="tb", input_schema={})],
    }
    factory = make_factory(tools)
    mcp_registry = MCPRegistry(servers, registry, client_factory=factory)

    await mcp_registry.start()
    assert "mcp:a:ta" in registry
    assert "mcp:b:tb" in registry

    await mcp_registry.stop()
    assert all(c.stopped for c in factory.built)
