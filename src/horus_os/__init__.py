"""horus-os: an open-source, self-hosted autonomous AI command center."""

from horus_os.agent import run_agent, run_agent_async
from horus_os.storage import Database, TraceRecord
from horus_os.tools import ToolRegistry, execute_tool_uses, read_file_tool
from horus_os.types import AgentResult, Tool, ToolResult, ToolUse

__version__ = "0.0.1"

__all__ = [
    "AgentResult",
    "Database",
    "Tool",
    "ToolRegistry",
    "ToolResult",
    "ToolUse",
    "TraceRecord",
    "__version__",
    "execute_tool_uses",
    "read_file_tool",
    "run_agent",
    "run_agent_async",
]
