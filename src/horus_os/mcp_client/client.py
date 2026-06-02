"""MCPClient: one connection to one configured MCP server (Pitfalls MC-1, MC-3).

`MCPClient` connects to a single allowlisted `MCPServerConfig` over one of
the three official transports (stdio subprocess, SSE, or Streamable HTTP),
runs `initialize()` then `list_tools()`, exposes the discovered descriptors,
and lets the agent call a tool by name. Every connection is the result of an
explicit `[[mcp.servers]]` allowlist entry (the MCP-03 trust gate lives in
`config.py`); this module never probes for servers on its own.

Two design constraints shape this module:

1. Lazy SDK import (Pitfall 12). The `mcp` package is imported INSIDE
   `start()`, never at module scope, so a bare `pip install horus-os`
   imports this file cleanly. A missing extra raises a clean
   `RuntimeError(MCP_EXTRA_HINT)`, never a bare `ModuleNotFoundError`,
   matching `otel_adapter.start()`.

2. Explicit cross-OS subprocess teardown (Pitfall MC-3 / SDK issue 1027).
   The stdio transport spawns a subprocess. On Windows the SDK's cleanup
   code after the `yield` in its lifespan can fail to run, orphaning the
   process. `stop()` therefore performs an EXPLICIT `terminate()` then
   bounded `wait()` then `kill()` on a process handle in a `finally`
   block that runs independently of the SDK context managers. The handle
   is a thin `_ProcessHandle` so the unit test can inject a fake that
   records the call sequence.

The session runs on a dedicated worker thread with its own asyncio event
loop. The SDK is fully async; the agent tool loop dispatches handlers
synchronously through `ToolRegistry.invoke`. Owning a private loop on a
private thread lets `call_tool` block on a coroutine via
`run_coroutine_threadsafe` without deadlocking the caller's loop (the
FastAPI lifespan loop or a worker thread in `execute_tool_uses`).
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any

from horus_os.mcp_client.config import MCPServerConfig

# Bound for the explicit teardown wait before escalating to kill() (MC-3).
MCP_TERMINATE_TIMEOUT_S = 5.0

# Clean install hint surfaced when the [mcp] extra is absent (Pitfall 12).
MCP_EXTRA_HINT = "MCP client requires 'pip install horus-os[mcp]'"


@dataclass(frozen=True)
class DiscoveredTool:
    """A tool descriptor advertised by an MCP server's tools/list response.

    A transport-neutral, SDK-free shape so the registry can build a
    horus-os `Tool` without importing the mcp package. `input_schema` is the
    raw JSON Schema object the server returned (may be empty).
    """

    name: str
    description: str
    input_schema: dict[str, Any]


class _ProcessHandle:
    """Thin sync teardown surface over a spawned MCP server subprocess.

    Exposes `terminate()`, `wait(timeout)`, `kill()`, and `is_running()`
    so `MCPClient.stop()` can drive an explicit, bounded teardown
    independent of the SDK lifespan (MC-3). The real stdio path wraps the
    SDK's anyio process; the unit test injects a fake implementing the same
    four methods to record the call sequence.
    """

    def __init__(self, process: Any, loop: asyncio.AbstractEventLoop) -> None:
        self._process = process
        self._loop = loop

    def terminate(self) -> None:
        self._process.terminate()

    def wait(self, timeout: float) -> bool:
        """Wait up to `timeout` seconds for exit. Return True if it exited.

        The anyio process exposes an async `wait()`. We drive it on the
        worker loop the process belongs to and bound it with
        `asyncio.wait_for` so a wedged server cannot hang teardown.
        """
        future = asyncio.run_coroutine_threadsafe(self._bounded_wait(timeout), self._loop)
        try:
            return bool(future.result(timeout=timeout + 1.0))
        except Exception:
            return self._process.returncode is not None

    async def _bounded_wait(self, timeout: float) -> bool:
        try:
            await asyncio.wait_for(self._process.wait(), timeout=timeout)
            return True
        except TimeoutError:
            return False

    def kill(self) -> None:
        self._process.kill()

    def is_running(self) -> bool:
        return self._process.returncode is None


class MCPClient:
    """Manages one connection to one configured MCP server.

    Constructed cheaply with just an `MCPServerConfig`; no SDK import and no
    connection happen until `start()`. `start()` brings up the transport,
    initializes the session, and caches the discovered tool descriptors.
    `call_tool` runs a server tool and flattens the result to a string.
    `stop()` performs the explicit MC-3 teardown and is idempotent.
    """

    def __init__(self, config: MCPServerConfig) -> None:
        self._config = config
        self._tools: list[DiscoveredTool] = []
        # Worker-thread / event-loop state, all allocated in start().
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._session: Any = None
        self._exit_stack: Any = None
        self._process: _ProcessHandle | None = None
        self._ready = threading.Event()
        self._start_error: BaseException | None = None
        self._stopped = False

    @property
    def name(self) -> str:
        return self._config.name

    def discovered_tools(self) -> list[DiscoveredTool]:
        """Return the tool descriptors cached at connect time."""
        return list(self._tools)

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        """Connect, initialize, and discover tools on a dedicated worker loop.

        Lazy-imports the mcp SDK (Pitfall 12). A missing [mcp] extra raises
        a clean `RuntimeError(MCP_EXTRA_HINT)`, never a bare
        `ModuleNotFoundError`. Any connect error from the worker loop is
        re-raised on the caller's thread so the registry can record it
        against this server.
        """
        try:
            import mcp  # noqa: F401  (presence-check only)
        except ImportError as exc:
            raise RuntimeError(MCP_EXTRA_HINT) from exc

        self._ready.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name=f"mcp-client-{self._config.name}", daemon=True
        )
        self._thread.start()
        # Wait for the worker loop to finish connect (success or failure).
        self._ready.wait()
        if self._start_error is not None:
            error = self._start_error
            # Tear the half-built worker loop down before surfacing.
            with contextlib.suppress(Exception):
                self.stop()
            raise error

    def _run_loop(self) -> None:
        """Worker-thread entry point: own an event loop for this client's life."""
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._connect())
        except BaseException as exc:
            self._start_error = exc
            self._ready.set()
            loop.close()
            return
        self._ready.set()
        # Keep the loop alive so call_tool coroutines can be scheduled onto
        # it until stop() requests shutdown.
        try:
            loop.run_forever()
        finally:
            loop.close()

    async def _connect(self) -> None:
        """Open the transport, initialize the session, and list tools.

        Uses an AsyncExitStack so the transport context manager and the
        ClientSession stay entered for the worker loop's lifetime; stop()
        unwinds the stack. For stdio we capture the spawned subprocess into
        a `_ProcessHandle` so teardown does not depend on the SDK lifespan
        (MC-3).
        """
        from contextlib import AsyncExitStack

        from mcp.client.sse import sse_client
        from mcp.client.stdio import stdio_client
        from mcp.client.streamable_http import streamablehttp_client

        from mcp import ClientSession, StdioServerParameters

        stack = AsyncExitStack()
        self._exit_stack = stack

        transport = self._config.transport
        if transport == "stdio":
            command = self._config.command or []
            if not command:
                raise ValueError(f"stdio server {self._config.name!r} has no command")
            params = StdioServerParameters(
                command=command[0],
                args=[*command[1:], *(self._config.args or [])],
                env=self._config.env,
            )
            read, write = await self._enter_stdio(stack, stdio_client, params)
        elif transport == "sse":
            if not self._config.url:
                raise ValueError(f"sse server {self._config.name!r} has no url")
            streams = await stack.enter_async_context(sse_client(self._config.url))
            read, write = streams[0], streams[1]
        elif transport == "streamable-http":
            if not self._config.url:
                raise ValueError(f"streamable-http server {self._config.name!r} has no url")
            # The SDK yields (read, write, get_session_id); destructure
            # defensively so a 2-tuple future variant still works.
            streams = await stack.enter_async_context(streamablehttp_client(self._config.url))
            read, write = streams[0], streams[1]
        else:  # pragma: no cover - guarded by config.SUPPORTED_TRANSPORTS
            raise ValueError(f"unsupported transport {transport!r}")

        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._session = session

        listing = await session.list_tools()
        self._tools = [
            DiscoveredTool(
                name=t.name,
                description=t.description or "",
                input_schema=dict(t.inputSchema or {}),
            )
            for t in listing.tools
        ]

    async def _enter_stdio(self, stack: Any, stdio_client: Any, params: Any) -> tuple[Any, Any]:
        """Enter stdio_client and capture the spawned process for teardown.

        The SDK's `stdio_client` spawns the subprocess internally and does
        not yield the handle. We briefly wrap the SDK's process-creation
        helper so we can stash the spawned anyio process in a
        `_ProcessHandle`, giving `stop()` an explicit, SDK-independent
        teardown path (MC-3 / SDK issue 1027). The wrap is removed
        immediately after the streams are entered.
        """
        import mcp.client.stdio as stdio_mod

        captured: list[Any] = []
        original = stdio_mod._create_platform_compatible_process

        async def _capturing(*args: Any, **kwargs: Any) -> Any:
            proc = await original(*args, **kwargs)
            captured.append(proc)
            return proc

        stdio_mod._create_platform_compatible_process = _capturing
        try:
            streams = await stack.enter_async_context(stdio_client(params))
        finally:
            stdio_mod._create_platform_compatible_process = original

        if captured and self._loop is not None:
            self._process = _ProcessHandle(captured[0], self._loop)
        return streams[0], streams[1]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call a server tool and flatten its result to a single string.

        Joins the `.text` of every TextContent block; falls back to the
        string form of `structuredContent` when there is no text content.
        This runs on the worker loop; the synchronous bridge for the agent
        tool loop is `call_tool_sync`.
        """
        if self._session is None:
            raise RuntimeError(f"MCP client {self._config.name!r} is not started")
        result = await self._session.call_tool(name, arguments)
        texts: list[str] = []
        for block in getattr(result, "content", None) or []:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                texts.append(text)
        if texts:
            return "\n".join(texts)
        structured = getattr(result, "structuredContent", None)
        if structured is not None:
            return str(structured)
        return ""

    def call_tool_sync(self, name: str, arguments: dict[str, Any]) -> str:
        """Synchronous bridge: run `call_tool` on the worker loop and block.

        Submits the coroutine to the client's dedicated loop via
        `run_coroutine_threadsafe`, so a handler dispatched synchronously by
        `ToolRegistry.invoke` (possibly already inside an event loop or a
        thread-pool worker) does not deadlock its own loop.
        """
        if self._loop is None:
            raise RuntimeError(f"MCP client {self._config.name!r} is not started")
        future: Future[str] = asyncio.run_coroutine_threadsafe(
            self.call_tool(name, arguments), self._loop
        )
        return future.result()

    def stop(self) -> None:
        """Tear the client down: explicit terminate/wait/kill, then close loop.

        Idempotent via `self._stopped`. The explicit subprocess teardown
        (MC-3) lives in a `finally` block so it runs regardless of how the
        SDK context managers behaved during stack unwind. Every step is
        guarded so a NoSuchProcess / already-exited race is swallowed.
        """
        if self._stopped:
            return
        self._stopped = True

        loop = self._loop
        try:
            # Unwind the SDK contexts (ClientSession, transport) on the
            # worker loop. Best effort: the explicit teardown below is the
            # load-bearing guarantee, not this.
            if loop is not None and self._exit_stack is not None and loop.is_running():
                with contextlib.suppress(Exception):
                    fut = asyncio.run_coroutine_threadsafe(self._exit_stack.aclose(), loop)
                    fut.result(timeout=MCP_TERMINATE_TIMEOUT_S)
        finally:
            # MC-3 explicit teardown, independent of the SDK lifespan.
            self._teardown_process()
            # Stop the worker loop and join the thread so no zombie loop
            # lingers. Guarded against the loop already being closed.
            if loop is not None:
                with contextlib.suppress(Exception):
                    loop.call_soon_threadsafe(loop.stop)
            thread = self._thread
            if thread is not None and thread.is_alive():
                with contextlib.suppress(Exception):
                    thread.join(timeout=MCP_TERMINATE_TIMEOUT_S)

    def _teardown_process(self) -> None:
        """Drive terminate() -> bounded wait() -> kill() on the process handle.

        Each call is guarded so a process that already exited (a
        NoSuchProcess-style race) does not raise out of teardown. On
        Windows, `terminate()` maps to TerminateProcess and `kill()` is the
        hard fallback when the process does not exit within the bound.
        """
        process = self._process
        if process is None:
            return
        with contextlib.suppress(Exception):
            process.terminate()
        exited = False
        with contextlib.suppress(Exception):
            exited = process.wait(MCP_TERMINATE_TIMEOUT_S)
        if not exited:
            with contextlib.suppress(Exception):
                if process.is_running():
                    process.kill()
        self._process = None
