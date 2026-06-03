"""MCPRegistry: LifecycleAdapter bridging configured servers into the registry.

`MCPRegistry` is the seam between the MCP transport layer and the rest of
horus-os. It holds one `MCPClient` per allowlisted `MCPServerConfig`, and on
`start()` it connects each client, sanitizes every advertised tool
description (Pitfall MC-2), and registers each discovered tool into the
shared `ToolRegistry` under a `mcp:{server}:{tool}` name via
`register_namespaced` (Pitfalls MC-1 / MC-4). On `stop()` it tears every
client down (Pitfall MC-3 / MCP-04).

It satisfies the `LifecycleAdapter` Protocol (name / async start / async
stop) so the FastAPI lifespan drives it exactly like `DiscordAdapter` and
`EmailAdapter`. Mirroring those adapters, a failing server or a
`CollisionError` is RECORDED against that server (and re-exposed via
`errors()`) rather than allowed to crash the lifespan, so one bad server
never denies the user their other servers. A `CollisionError` is never
swallowed silently: it is observable to the caller and to tests.

The trust gate is enforced here too: an empty `servers` list builds no
clients and registers nothing (MCP-03 fast path).
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

from horus_os.mcp_client.client import MCPClient
from horus_os.mcp_client.config import MCPServerConfig
from horus_os.mcp_client.sanitize import sanitize_tool_description
from horus_os.tools.registry import CollisionError, ToolRegistry
from horus_os.types import Tool

if TYPE_CHECKING:
    from horus_os.adapters.base import AdapterContext


class MCPRegistry:
    """LifecycleAdapter that registers MCP tools into the shared ToolRegistry.

    Constructed with the allowlisted server configs, the shared
    `ToolRegistry`, and (optionally) a `client_factory` so tests can inject
    a fake client. The reserved builtin-name set is computed from the names
    already present in the registry at construction time: every tool
    registered before MCP wiring is a builtin an MCP server must not shadow.
    """

    name = "mcp"

    def __init__(
        self,
        servers: list[MCPServerConfig],
        tool_registry: ToolRegistry,
        *,
        client_factory: Any | None = None,
    ) -> None:
        self._servers = list(servers)
        self._tool_registry = tool_registry
        # Snapshot the builtin names BEFORE any MCP tool is added; these are
        # the reserved names register_namespaced refuses to shadow (MC-4).
        self._builtin_names: set[str] = {t.name for t in tool_registry.list()}
        self._factory = client_factory or MCPClient
        self._clients: list[MCPClient] = []
        self._errors: dict[str, str] = {}

    def errors(self) -> dict[str, str]:
        """Return a copy of recorded per-server errors (server name -> message).

        A `CollisionError` or a connect failure is recorded here so the
        caller and tests can observe it; it is NOT swallowed silently.
        """
        return dict(self._errors)

    async def start(self, context: AdapterContext | None = None) -> None:
        """Connect each server and register its sanitized, namespaced tools.

        Empty config returns immediately having registered nothing (the
        MCP-03 trust-gate fast path). Each server's connect-and-register is
        isolated: a failure or `CollisionError` is recorded against that
        server and the loop continues, mirroring `DiscordAdapter`.
        """
        if not self._servers:
            return

        for server in self._servers:
            client = self._factory(server)
            try:
                await self._start_client(client)
                self._register_tools(server, client)
            except CollisionError as exc:
                # MC-4: a builtin-name collision must surface, not be
                # swallowed. Record it and tear this client back down.
                self._errors[server.name] = str(exc)
                await self._stop_client(client)
                continue
            except Exception as exc:
                self._errors[server.name] = f"{type(exc).__name__}: {exc}"
                await self._stop_client(client)
                continue
            self._clients.append(client)

    async def _start_client(self, client: MCPClient) -> None:
        """Run the (synchronous) client start without blocking the event loop.

        `MCPClient.start()` drives its own worker loop and blocks until the
        connection is ready; offloading to a thread keeps the caller's event
        loop responsive.
        """
        await asyncio.to_thread(client.start)

    def _register_tools(self, server: MCPServerConfig, client: MCPClient) -> None:
        """Build a namespaced, sanitized Tool per discovered descriptor.

        The handler closure bridges back into the MCP session synchronously
        via `client.call_tool_sync`, so `execute_tool_uses` traces every MCP
        call through the existing tool_invocations path with no new schema
        (MCP-01). A `CollisionError` from `register_namespaced` propagates to
        the caller in `start()`, which records it (MC-4).
        """
        for descriptor in client.discovered_tools():
            tool = Tool(
                name=f"mcp:{server.name}:{descriptor.name}",
                description=sanitize_tool_description(descriptor.description),
                parameters=descriptor.input_schema or {"type": "object", "properties": {}},
                handler=self._make_handler(client, descriptor.name),
            )
            self._tool_registry.register_namespaced(tool, self._builtin_names)

    @staticmethod
    def _make_handler(client: MCPClient, tool_name: str) -> Any:
        """Build a synchronous handler that calls the MCP tool and returns a str.

        Captures the client and the bare (un-prefixed) tool name; the MCP
        server expects its own name, not the `mcp:{server}:` prefix.
        """

        def handler(**kwargs: Any) -> str:
            return client.call_tool_sync(tool_name, kwargs)

        return handler

    async def stop(self) -> None:
        """Tear down every client (MCP-04 batch teardown entry point).

        Iterates in reverse and swallows per-client teardown exceptions so
        one bad teardown cannot block the others.
        """
        for client in reversed(self._clients):
            await self._stop_client(client)
        self._clients = []

    @staticmethod
    async def _stop_client(client: MCPClient) -> None:
        """Stop one client off the event loop, swallowing teardown errors."""
        with contextlib.suppress(Exception):
            await asyncio.to_thread(client.stop)
