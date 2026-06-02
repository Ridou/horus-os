"""A minimal real stdio MCP server for the cross-OS teardown proof (TEST-34).

This is a tiny, dependency-light MCP server launched as a subprocess via
`sys.executable tests/mcp/stub_mcp_server.py`. It answers the MCP handshake
(`initialize` and `tools/list`, advertising one trivial `ping` tool) and then
blocks on stdin, staying alive until its parent terminates it. That keeps the
subprocess running long enough for `MCPClient.stop()` /
`MCPRegistry.stop()` to exercise the explicit terminate/wait/kill teardown
(Pitfall MC-3 / MCP-04) and prove no zombie remains on macOS, Ubuntu, and
Windows.

It uses the official `mcp` SDK's `FastMCP` server so the wire protocol is
exactly what a real server speaks; there is zero Node / npx dependency, so the
test runs identically on every CI runner. Running it via `sys.executable`
keeps the spawn cross-OS (no shell, no bash).
"""

from __future__ import annotations


def main() -> None:
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("horus-os-stub")

    @server.tool()
    def ping() -> str:
        """Return a fixed string so the client can prove a call round-trips."""
        return "pong"

    # run("stdio") reads framed JSON-RPC from stdin and writes to stdout,
    # blocking until the transport closes (parent terminate/kill). This is the
    # long-lived child whose teardown the test asserts.
    server.run("stdio")


if __name__ == "__main__":
    main()
