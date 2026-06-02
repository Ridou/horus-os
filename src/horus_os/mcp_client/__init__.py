"""MCP client package: opt-in bridge from MCP servers into the tool registry.

This package connects to explicitly-allowlisted MCP servers, sanitizes their
tool descriptions, and registers each discovered tool into the shared
`ToolRegistry` under a `mcp:{server}:{tool}` namespace so the agent loop
traces MCP calls exactly like builtins. The trust model is the first design
decision (Pitfall MC-1 is BLOCKING): an empty or absent `mcp.toml` registers
ZERO tools; only a `[[mcp.servers]]` block activates a server.

Public surface:
- `MCPServerConfig` / `default_mcp_config_path` (config + trust gate)
- `MCPClient` (one connection, explicit cross-OS teardown)
- `MCPRegistry` (LifecycleAdapter bridging config to namespaced tools)
- `sanitize_tool_description` (MC-2 tool-poisoning defense)
"""

from __future__ import annotations

from horus_os.mcp_client.client import MCP_EXTRA_HINT, MCPClient
from horus_os.mcp_client.config import MCPServerConfig, default_mcp_config_path
from horus_os.mcp_client.registry import MCPRegistry
from horus_os.mcp_client.sanitize import (
    MCP_DESCRIPTION_MAX_CHARS,
    sanitize_tool_description,
)

__all__ = [
    "MCP_DESCRIPTION_MAX_CHARS",
    "MCP_EXTRA_HINT",
    "MCPClient",
    "MCPRegistry",
    "MCPServerConfig",
    "default_mcp_config_path",
    "sanitize_tool_description",
]
