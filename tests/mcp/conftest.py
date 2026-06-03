"""Shared fixtures and fakes for the MCP client unit suite (TEST-34 slice).

These doubles let the suite exercise namespacing, the opt-in trust gate,
sanitization, and the teardown call sequence WITHOUT a real network, a real
MCP server, or a model download. Every external boundary is mocked:

- `FakeProcess` records terminate/wait/kill so the MC-3 teardown sequence
  is assertable without spawning a subprocess.
- `FakeMCPClient` advertises a fixed tool list and records call_tool args so
  the registry's namespacing, sanitization, and handler bridge are testable
  in-process.

The real cross-OS no-zombie subprocess proof lands in plan 71-02.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from horus_os.mcp_client.client import DiscoveredTool
from horus_os.mcp_client.config import MCPServerConfig


class FakeProcess:
    """Records terminate/wait/kill calls for the MC-3 teardown unit test.

    `exit_on_terminate` controls whether `wait()` reports the process as
    exited (True) or still-running (False). When still-running, the teardown
    path escalates to `kill()`, which this fake records.
    """

    def __init__(self, *, exit_on_terminate: bool = True) -> None:
        self.calls: list[str] = []
        self._exit_on_terminate = exit_on_terminate
        self._terminated = False
        self._killed = False

    def terminate(self) -> None:
        self.calls.append("terminate")
        self._terminated = True

    def wait(self, timeout: float) -> bool:
        self.calls.append("wait")
        # Report exited only when the fake was configured to exit on
        # terminate; otherwise the teardown must escalate to kill().
        return self._terminated and self._exit_on_terminate

    def kill(self) -> None:
        self.calls.append("kill")
        self._killed = True

    def is_running(self) -> bool:
        return not (self._killed or (self._terminated and self._exit_on_terminate))


@dataclass
class FakeMCPClient:
    """In-process stand-in for MCPClient used by registry tests.

    Built from an `MCPServerConfig` (matching the real factory signature) and
    a class-level `tools` template the test sets before construction. Records
    every `call_tool_sync` invocation and whether `stop()` was called.
    """

    config: MCPServerConfig
    tools: list[DiscoveredTool] = field(default_factory=list)
    started: bool = False
    stopped: bool = False
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    call_result: str = "fake-result"

    @property
    def name(self) -> str:
        return self.config.name

    def start(self) -> None:
        self.started = True

    def discovered_tools(self) -> list[DiscoveredTool]:
        return list(self.tools)

    def call_tool_sync(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, dict(arguments)))
        return self.call_result

    def stop(self) -> None:
        self.stopped = True


def make_factory(tools_by_server: dict[str, list[DiscoveredTool]]):
    """Return a client_factory that yields FakeMCPClient configured per server.

    `tools_by_server` maps a server name to the tool descriptors that server
    should advertise. The returned factory also stashes each built client on
    a `.built` list so a test can assert teardown and call-through.
    """
    built: list[FakeMCPClient] = []

    def factory(config: MCPServerConfig) -> FakeMCPClient:
        client = FakeMCPClient(
            config=config,
            tools=list(tools_by_server.get(config.name, [])),
        )
        built.append(client)
        return client

    factory.built = built  # type: ignore[attr-defined]
    return factory
