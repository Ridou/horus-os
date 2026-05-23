"""horus-os: an open-source, self-hosted autonomous AI command center."""

from horus_os.agent import run_agent, run_agent_async, run_agent_loop
from horus_os.config import Config
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

__version__ = "0.1.0"


def create_app(data_dir=None):
    """Lazy re-export of `horus_os.server.create_app` to avoid loading FastAPI at import time."""
    from horus_os.server import create_app as _create_app

    return _create_app(data_dir)


__all__ = [
    "AgentResult",
    "Config",
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
    "create_app",
    "create_note_tool",
    "execute_tool_uses",
    "list_notes_tool",
    "read_file_tool",
    "read_note_tool",
    "run_agent",
    "run_agent_async",
    "run_agent_loop",
    "search_notes_tool",
]
