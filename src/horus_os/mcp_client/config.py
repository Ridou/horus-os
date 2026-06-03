"""MCP server configuration and the opt-in trust gate (Pitfall MC-1, MCP-03).

The MCP spec defines tool discovery but no authorization layer. A naive
client connects to every reachable server and registers every discovered
tool, handing an untrusted subprocess or remote endpoint full access to the
tool registry. horus-os refuses that posture: the `mcp.toml` allowlist is the
ONLY activation surface. No file means no servers, no network probe, no
tools. Adding a `[[mcp.servers]]` block is the single conscious act that
turns a server on.

`MCPServerConfig.load(path)` therefore returns an EMPTY list when the path
does not exist or carries no `[[mcp.servers]]` entries. It mirrors the
`config.py` tomllib + pathlib idiom and the `discover_adapters` resilience
rule: a malformed or unsupported server entry is skipped (never crashes the
load), so one bad block cannot deny the user their other servers.

TOML shape (nested under a top-level `[mcp]` table)::

    [[mcp.servers]]
    name = "filesystem"
    transport = "stdio"
    command = ["npx", "@modelcontextprotocol/server-filesystem", "/tmp"]

    [[mcp.servers]]
    name = "remote"
    transport = "streamable-http"
    url = "http://localhost:8000/mcp"
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

MCP_CONFIG_FILENAME = "mcp.toml"

# The three transports the official mcp SDK supports. WebSocket is excluded
# on purpose: the spec deprecated it in favor of Streamable HTTP, and an
# entry naming an unsupported transport is skipped at load time so it never
# reaches the client.
SUPPORTED_TRANSPORTS = ("stdio", "sse", "streamable-http")


@dataclass(frozen=True)
class MCPServerConfig:
    """One explicitly-allowlisted MCP server.

    `transport` is one of SUPPORTED_TRANSPORTS. `command`/`args`/`env` apply
    to the stdio transport (a spawned subprocess); `url` applies to the sse
    and streamable-http transports (a remote or local HTTP endpoint). The
    dataclass is frozen so a loaded config cannot be mutated in place.
    """

    name: str
    transport: str
    command: list[str] | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    url: str | None = None

    @classmethod
    def load(cls, path: Path) -> list[MCPServerConfig]:
        """Load `[[mcp.servers]]` entries from `path`, default-empty on absence.

        Returns `[]` when:
        - the path does not exist (the MCP-03 trust gate: no file means no
          servers and no network probe), or
        - the file parses but has no `[mcp].servers` array, or
        - every entry is malformed or names an unsupported transport.

        Each surviving entry is validated (`name` present, `transport` in
        SUPPORTED_TRANSPORTS) and built into an `MCPServerConfig`. A single
        bad entry is skipped, not fatal, mirroring `discover_adapters`.
        """
        if not path.exists():
            return []

        try:
            with path.open("rb") as fh:
                data = tomllib.load(fh)
        except (OSError, tomllib.TOMLDecodeError):
            # An unreadable or malformed file is treated as "no servers"
            # rather than a hard crash; the trust gate stays closed.
            return []

        mcp_table = data.get("mcp")
        if not isinstance(mcp_table, dict):
            return []
        raw_servers = mcp_table.get("servers")
        if not isinstance(raw_servers, list):
            return []

        configs: list[MCPServerConfig] = []
        for entry in raw_servers:
            config = cls._from_entry(entry)
            if config is not None:
                configs.append(config)
        return configs

    @classmethod
    def _from_entry(cls, entry: object) -> MCPServerConfig | None:
        """Build one MCPServerConfig from a raw TOML table, or None if invalid.

        Skips (returns None for) any entry that is not a table, lacks a
        string `name`, or names a transport outside SUPPORTED_TRANSPORTS.
        Returning None keeps the loader resilient: a bad block is dropped
        instead of aborting the whole load.
        """
        if not isinstance(entry, dict):
            return None
        name = entry.get("name")
        transport = entry.get("transport")
        if not isinstance(name, str) or not name:
            return None
        if transport not in SUPPORTED_TRANSPORTS:
            return None

        command = entry.get("command")
        if command is not None and not isinstance(command, list):
            command = None
        args = entry.get("args")
        if args is not None and not isinstance(args, list):
            args = None
        env = entry.get("env")
        if env is not None and not isinstance(env, dict):
            env = None
        url = entry.get("url")
        if url is not None and not isinstance(url, str):
            url = None

        return cls(
            name=name,
            transport=transport,
            command=list(command) if command is not None else None,
            args=list(args) if args is not None else None,
            env=dict(env) if env is not None else None,
            url=url,
        )


def default_mcp_config_path(data_dir: Path) -> Path:
    """Return the default mcp.toml location under `data_dir`.

    The single source of truth for where the allowlist lives, so the CLI,
    the registry, and `horus-os doctor` all agree on the path.
    """
    return data_dir / MCP_CONFIG_FILENAME
