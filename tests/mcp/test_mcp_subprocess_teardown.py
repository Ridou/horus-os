"""Cross-OS real-subprocess no-zombie teardown proof (TEST-34 / MCP-04 / MC-3).

This is the load-bearing security test for Pitfall MC-3: a stdio MCP server is
a real child process whose OS handles and memory must be reclaimed at shutdown
on EVERY supported OS, especially Windows where the SDK's lifespan cleanup
after `yield` can fail and orphan the process (SDK issue 1027).

Unlike the 71-01 unit teardown test (which drives terminate/wait/kill on a
FAKE process object), this spawns a REAL stdio MCP server subprocess via
`sys.executable tests/mcp/stub_mcp_server.py`, records its PID, calls stop(),
and asserts the process is no longer alive on the CURRENT OS. It is structured
to run as-is on macOS, Ubuntu, and Windows in the 3-OS x 2-python CI matrix:
there is NO pytest.mark.skipif for Windows. The liveness probe is portable
(the process-handle returncode), with an extra POSIX-only os.kill(pid, 0)
ProcessLookupError assertion where that signal is meaningful.

The stub uses the official mcp SDK's FastMCP server, so there is zero Node /
npx dependency and the spawn is shell-free and cross-OS.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

# The stub MCP server subprocess imports the official mcp SDK ([mcp] extra).
# Skip when absent (the bare [dev] CI install); the [all] install-smoke
# variant installs the SDK.
pytest.importorskip("mcp")

from horus_os.mcp_client.client import MCPClient
from horus_os.mcp_client.config import MCPServerConfig
from horus_os.mcp_client.registry import MCPRegistry

# Path to the vendored stub server, launched via sys.executable so the spawn is
# identical on every OS (no bash, no npx).
STUB_SERVER = Path(__file__).parent / "stub_mcp_server.py"


def _stub_config(name: str = "stub") -> MCPServerConfig:
    return MCPServerConfig(
        name=name,
        transport="stdio",
        command=[sys.executable, str(STUB_SERVER)],
    )


def _underlying_process(client: MCPClient):
    """Return the spawned anyio process handle captured by MCPClient.start()."""
    handle = client._process
    assert handle is not None, "stdio MCPClient.start() did not capture a subprocess handle"
    return handle._process


def _process_dead(process) -> bool:
    """Portable liveness check: the process has a non-None returncode.

    The anyio subprocess exposes `returncode`, which stays None while running
    and becomes the exit status once the process has been reaped. This works
    identically on POSIX and Windows, so the assertion needs no OS branch.
    """
    return process.returncode is not None


def _wait_dead(process, timeout: float = 5.0) -> bool:
    """Poll the portable liveness check until the process is dead or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _process_dead(process):
            return True
        time.sleep(0.05)
    return _process_dead(process)


def test_stdio_subprocess_dead_after_stop() -> None:
    """A real stdio MCP subprocess is proven dead after stop() on the current OS.

    Spawns the stub server through a one-server MCPRegistry, records the PID,
    confirms the tool was discovered and round-trips, calls MCPRegistry.stop()
    (the same teardown path the FastAPI lifespan drives), and asserts no zombie
    remains. Runs on macOS, Ubuntu, and Windows with no skip (TEST-34).
    """
    import asyncio

    from horus_os.tools.registry import ToolRegistry

    tool_registry = ToolRegistry()
    mcp_registry = MCPRegistry([_stub_config()], tool_registry)

    asyncio.run(mcp_registry.start())

    # The stub advertised exactly one tool, registered under its namespace.
    registered = [t.name for t in tool_registry.list()]
    assert "mcp:stub:ping" in registered

    # Capture the live subprocess BEFORE teardown.
    client = mcp_registry._clients[0]
    process = _underlying_process(client)
    pid = process.pid
    assert pid is not None
    assert not _process_dead(process), "stub subprocess should be alive before stop()"

    # The same teardown the lifespan finally-block runs.
    async def _stop() -> None:
        await mcp_registry.stop()

    asyncio.run(_stop())

    # Portable cross-OS assertion: the process has a returncode now.
    assert _wait_dead(process), f"subprocess pid={pid} is still alive after stop() (zombie)"

    # Extra POSIX-only proof: os.kill(pid, 0) raises ProcessLookupError once the
    # process is gone. On Windows os.kill semantics differ, so this assertion is
    # guarded to POSIX, but the portable returncode assertion above runs on ALL
    # three OSes with no skip.
    if os.name == "posix":
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


def test_stop_twice_is_idempotent() -> None:
    """Calling stop() twice does not raise and leaves no process alive.

    Spawns a real stub server through a bare MCPClient, stops it twice, and
    asserts the second stop() is a no-op and the subprocess is still dead.
    """
    client = MCPClient(_stub_config(name="idem"))
    client.start()
    process = _underlying_process(client)
    pid = process.pid

    client.stop()
    assert _wait_dead(process), f"subprocess pid={pid} alive after first stop()"

    # Second stop() must be a no-op: no raise, still dead.
    client.stop()
    assert _process_dead(process)
    if os.name == "posix":
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
