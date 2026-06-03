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
class ToolCallEvent:
    """Synthetic event emitted by `run_agent_stream` when the model requests a tool call.

    Unlike `ToolUse`, this is not a record of a turn's parsed response. It is a
    notification surfaced mid-stream so consumers (CLI, dashboard) can observe
    that the model asked for a tool without `run_agent_stream` itself dispatching
    it. Tool execution remains the responsibility of `run_agent_loop`.
    """

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


@dataclass
class ShellInvocation:
    """A persisted record of one gated shell command execution (SHELL-02).

    Mirrors the NoteWrite shape: one row per run, written on every code path
    (clean run, metacharacter reject, boundary reject, timeout). `exit_code` is
    None when the process was killed by the timeout. `command` is the joined
    args list kept for display only; the structured args never reach a shell.
    """

    invocation_id: str
    created_at: str  # ISO-8601 UTC
    command: str  # the joined [command, *args] for display
    exit_code: int | None  # None when killed by the timeout
    stdout_truncated: str
    working_directory: str
    trace_id: str | None = None


@dataclass
class AgentProfile:
    """A named agent configuration stored in the database."""

    name: str
    system_prompt: str
    default_model: str | None = None
    allowed_tools: list[str] | None = None  # None means unrestricted
    memory_scope: str | None = None  # opaque, deferred to Phase 13
    created_at: str = ""  # ISO-8601 UTC, set by Database methods
    updated_at: str = ""  # ISO-8601 UTC, set by Database methods
    color: str | None = None  # hex accent for the dashboard, e.g. "#00d4ff"
    description: str | None = None  # one-line summary of what the agent does
    soul_path: str | None = None  # notes_dir-relative path to the SOUL.md persona
