"""MCPServerConfig loader unit tests (Pitfall MC-1 / MCP-03 trust gate).

Pins parsing of `[[mcp.servers]]` blocks, the default-empty-on-absence
trust gate, and the skip-on-unsupported-transport resilience rule.
"""

from __future__ import annotations

from pathlib import Path

from horus_os.mcp_client.config import (
    SUPPORTED_TRANSPORTS,
    MCPServerConfig,
    default_mcp_config_path,
)

_TWO_SERVERS = """
[[mcp.servers]]
name = "filesystem"
transport = "stdio"
command = ["npx", "@modelcontextprotocol/server-filesystem", "/tmp"]
args = ["--verbose"]

[[mcp.servers]]
name = "remote"
transport = "streamable-http"
url = "http://localhost:8000/mcp"
"""


def test_parse_two_servers(tmp_path: Path) -> None:
    path = tmp_path / "mcp.toml"
    path.write_text(_TWO_SERVERS, encoding="utf-8")

    configs = MCPServerConfig.load(path)
    assert len(configs) == 2

    by_name = {c.name: c for c in configs}
    stdio = by_name["filesystem"]
    assert stdio.transport == "stdio"
    assert stdio.command == ["npx", "@modelcontextprotocol/server-filesystem", "/tmp"]
    assert stdio.args == ["--verbose"]
    assert stdio.url is None

    http = by_name["remote"]
    assert http.transport == "streamable-http"
    assert http.url == "http://localhost:8000/mcp"
    assert http.command is None


def test_unsupported_transport_skipped(tmp_path: Path) -> None:
    path = tmp_path / "mcp.toml"
    path.write_text(
        """
[[mcp.servers]]
name = "good"
transport = "stdio"
command = ["echo"]

[[mcp.servers]]
name = "ws"
transport = "websocket"
url = "ws://localhost:9000"
""",
        encoding="utf-8",
    )

    configs = MCPServerConfig.load(path)
    names = {c.name for c in configs}
    assert "good" in names
    assert "ws" not in names
    # The loader never returns a config with an unsupported transport.
    assert all(c.transport in SUPPORTED_TRANSPORTS for c in configs)


def test_entry_missing_name_skipped(tmp_path: Path) -> None:
    path = tmp_path / "mcp.toml"
    path.write_text(
        """
[[mcp.servers]]
transport = "stdio"
command = ["echo"]
""",
        encoding="utf-8",
    )
    assert MCPServerConfig.load(path) == []


def test_malformed_toml_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "mcp.toml"
    path.write_text("this is not = valid = toml [[[", encoding="utf-8")
    # The trust gate stays closed on a malformed file (no crash, no servers).
    assert MCPServerConfig.load(path) == []


def test_default_mcp_config_path() -> None:
    data_dir = Path("/tmp/horus-data")
    assert default_mcp_config_path(data_dir) == data_dir / "mcp.toml"
