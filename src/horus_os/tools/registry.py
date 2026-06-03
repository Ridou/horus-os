"""Tool registry.

The registry holds `Tool` objects keyed by name. Callers register tools
once at startup and look them up when the model returns a tool_use.
Registration is duplicate-safe by default; pass `replace=True` to
overwrite an existing entry.

`register_namespaced` is the MCP path (Pitfall MC-4). An MCP server picks
its own tool names; the protocol does not namespace them, so a hostile or
careless server can advertise a tool called `read_file` that would shadow
a horus-os builtin. Every MCP tool is therefore registered under a
server-scoped `mcp:{server}:{tool}` name, and `register_namespaced` REFUSES
to register any candidate whose name would collide with a reserved builtin,
raising `CollisionError`. The error MUST surface to the caller; it is never
swallowed, so the user learns that a server tried to shadow a builtin
instead of silently getting the untrusted tool.
"""

from __future__ import annotations

from typing import Any

from horus_os.types import Tool


class CollisionError(Exception):
    """Raised when an MCP tool name would shadow a reserved builtin (MC-4).

    `register_namespaced` raises this instead of silently overwriting a
    builtin or silently skipping the MCP tool. The message names both the
    offending tool and the builtin it would shadow so the user can act.
    """


class ToolRegistry:
    """In-memory map of tool name to `Tool` object."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool, *, replace: bool = False) -> None:
        """Add `tool` to the registry. Raises ValueError on duplicate unless replace=True."""
        if not replace and tool.name in self._tools:
            raise ValueError(f"Tool {tool.name!r} is already registered")
        self._tools[tool.name] = tool

    def register_namespaced(self, tool: Tool, builtin_names: set[str]) -> None:
        """Register an MCP tool, refusing any builtin-name collision (MC-4).

        `tool.name` is the FINAL registered name the caller built, normally
        the `mcp:{server}:{tool}` prefixed form. `builtin_names` is the
        reserved set of builtin tool names an MCP server must never shadow.

        The prefix is exactly what disambiguates an MCP tool from a builtin:
        a server `fs` advertising a tool `read_file` is stored under
        `mcp:fs:read_file`, which does NOT equal the builtin `read_file`, so
        it registers cleanly and leaves the builtin authoritative.

        Raises `CollisionError` (and registers NOTHING) when the final
        registered name itself equals a reserved builtin name. That is the
        unprefixed-collision case the MCP path must refuse: a caller that
        let an unprefixed builtin name through, or any future name that
        would land directly on a builtin. The error names both the offending
        tool and the builtin it would shadow, and it PROPAGATES to the
        caller; it is never swallowed.

        On success the tool is stored via the same duplicate-safe map used
        by `register`; a duplicate name raises `ValueError` exactly as
        `register` would.
        """
        if tool.name in builtin_names:
            raise CollisionError(
                f"MCP tool {tool.name!r} would shadow builtin {tool.name!r}; refusing to register"
            )
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name!r} is already registered")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Remove a tool by name. No-op if the name is not registered."""
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        """Return the registered tool or None."""
        return self._tools.get(name)

    def list(self) -> list[Tool]:
        """Return all registered tools in insertion order."""
        return list(self._tools.values())

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def invoke(self, name: str, tool_input: dict[str, Any]) -> Any:
        """Look up the tool and call its handler with the input dict.

        Raises KeyError if the tool is not registered. Raises
        RuntimeError if the tool exists but has no handler.
        """
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Tool {name!r} is not registered")
        if tool.handler is None:
            raise RuntimeError(f"Tool {name!r} has no handler")
        return tool.handler(**tool_input)
