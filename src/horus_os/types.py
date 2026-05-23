"""Shared data types for the horus-os agent runtime."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Tool:
    """A capability the agent can invoke.

    `parameters` is a JSON Schema object describing the inputs the model
    must produce. `handler` is the Python callable that runs when the
    tool is selected. Phase 02 captures the model's tool_use intent but
    does not auto-invoke the handler; the full execution loop lands in
    Phase 04.
    """

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any] | None = None


@dataclass
class ToolUse:
    """A single tool invocation the model requested."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass
class AgentResult:
    """Normalized result of a single agent turn."""

    text: str
    tool_uses: list[ToolUse] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
