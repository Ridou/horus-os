"""Tool registry.

The registry holds `Tool` objects keyed by name. Callers register tools
once at startup and look them up when the model returns a tool_use.
Registration is duplicate-safe by default; pass `replace=True` to
overwrite an existing entry.
"""

from __future__ import annotations

from typing import Any

from horus_os.types import Tool


class ToolRegistry:
    """In-memory map of tool name to `Tool` object."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool, *, replace: bool = False) -> None:
        """Add `tool` to the registry. Raises ValueError on duplicate unless replace=True."""
        if not replace and tool.name in self._tools:
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
