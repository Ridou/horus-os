"""horus-os: an open-source, self-hosted autonomous AI command center."""

from horus_os.agent import run_agent, run_agent_async
from horus_os.memory import (
    NotesStore,
    append_note_tool,
    create_note_tool,
    list_notes_tool,
    read_note_tool,
    search_notes_tool,
)
from horus_os.storage import Database, TraceRecord
from horus_os.tools import ToolRegistry, execute_tool_uses, read_file_tool
from horus_os.types import (
    AgentResult,
    NoteRef,
    NoteWrite,
    Tool,
    ToolResult,
    ToolUse,
)

__version__ = "0.0.1"

__all__ = [
    "AgentResult",
    "Database",
    "NoteRef",
    "NoteWrite",
    "NotesStore",
    "Tool",
    "ToolRegistry",
    "ToolResult",
    "ToolUse",
    "TraceRecord",
    "__version__",
    "append_note_tool",
    "create_note_tool",
    "execute_tool_uses",
    "list_notes_tool",
    "read_file_tool",
    "read_note_tool",
    "run_agent",
    "run_agent_async",
    "search_notes_tool",
]
