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
    tool is selected.
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
class ToolResult:
    """The outcome of running a single tool_use through a registry handler."""

    tool_use_id: str
    name: str
    output: Any = None
    error: str | None = None
    latency_ms: int | None = None


@dataclass
class AgentResult:
    """Normalized result of a single agent turn."""

    text: str
    tool_uses: list[ToolUse] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


@dataclass
class NoteRef:
    """A pointer to a markdown note in a NotesStore."""

    path: str  # relative path inside notes_dir, posix style
    title: str
    size_bytes: int
    modified_at: str  # ISO-8601 UTC
    preview: str


@dataclass
class NoteWrite:
    """A persisted record of one write to the notes folder."""

    write_id: str
    created_at: str  # ISO-8601 UTC
    operation: str  # "create" | "append"
    rel_path: str
    bytes_before: int
    bytes_after: int
    content: str
    trace_id: str | None = None
