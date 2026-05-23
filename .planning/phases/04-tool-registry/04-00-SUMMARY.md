---
phase: 04-tool-registry
plan: "00"
subsystem: tool-registry
tags: [tool-registry, builtin-tools, read-file, sandboxing, execute-loop]

# Dependency graph
requires:
  - phase: "02-agent-runtime-core"
    provides: "Tool dataclass, AgentResult.tool_uses populated by both provider modules"
  - phase: "03-persistence-layer"
    provides: "Database, used by callers as the on_log target for execute_tool_uses"
provides:
  - "horus_os.tools.ToolRegistry, name-keyed map of Tool with register / unregister / get / list / invoke / __contains__ / __len__"
  - "horus_os.tools.read_file_tool(base_dir=None), built-in factory with optional sandboxing"
  - "horus_os.tools.execute_tool_uses(registry, result, *, on_log=None), single-turn handler-execution helper"
  - "horus_os.types.ToolResult(tool_use_id, name, output, error, latency_ms)"
affects:
  - "Phase 07 (CLI) will register read_file_tool by default and pipe results into a multi-turn loop"
  - "Phase 08 (dashboard) will render ToolResult.output and error fields per trace"
  - "Phase 09 (setup wizard) will choose the base_dir for the sandboxed read_file tool"

# Tech tracking
tech-stack:
  added: []  # pure stdlib, no new deps
  patterns:
    - "Registry as a single name to Tool map. No category, no tags, no priority. Add complexity only when needed."
    - "Sandboxed file access via base_dir resolution check rather than chroot. Lightweight, works on every OS."
    - "Single-turn execute helper, not full multi-turn agent loop. Loop ownership stays with the surface (CLI, dashboard) that owns conversation state."
    - "Optional on_log callback receives each outcome. Lets callers persist to Database without tying the registry to storage."

key-files:
  created:
    - "src/horus_os/tools/__init__.py, 7 lines, re-exports"
    - "src/horus_os/tools/registry.py, 56 lines, ToolRegistry class"
    - "src/horus_os/tools/builtin.py, 55 lines, read_file_tool factory"
    - "src/horus_os/tools/loop.py, 49 lines, execute_tool_uses + _call_logger"
    - "tests/test_tool_registry.py, 95 lines, 9 tests"
    - "tests/test_tool_builtin.py, 74 lines, 7 tests"
    - "tests/test_tool_loop.py, 113 lines, 7 tests"
  modified:
    - "src/horus_os/types.py, added ToolResult dataclass"
    - "src/horus_os/__init__.py, re-exports ToolRegistry, ToolResult, execute_tool_uses, read_file_tool"

key-decisions:
  - "Registry stores Tool objects, not (name, handler) pairs. The Tool dataclass is the canonical shape and travels through providers, registry, and storage unchanged."
  - "Duplicate registration raises ValueError by default. The opt-in replace=True is for hot-reload scenarios and tests. Silent overwrite would mask configuration bugs."
  - "execute_tool_uses catches BaseException, not Exception. KeyboardInterrupt and SystemExit raised by a handler still become a ToolResult.error so the model can see what happened. The user can still ctrl-c the parent process because the catch is on the handler call, not on the loop."
  - "read_file_tool with no base_dir grants full read access to the user account running horus-os. This is intentional for the personal-command-center use case where the user explicitly grants permission. CLI and dashboard wiring (Phase 07, 08) will default to a sandboxed configuration via the setup wizard (Phase 09)."
  - "Path traversal check uses Path.resolve() and parent containment, not string prefix comparison. The string check would miss symlink traversal and the Windows short-name escape."
  - "on_log logger errors are swallowed. A user with a broken logger gets degraded observability, not a broken agent."

patterns-established:
  - "Built-in tools live in `tools/builtin.py` as factory functions. Each takes configuration (like base_dir) and returns a Tool. Callers register tools at startup, not at runtime."
  - "Test helpers (_tool, _result, _registry_with) keep test setup short and consistent."
  - "Sandboxing is a per-tool concern, not a registry concern. The registry holds whatever you give it; security lives in the tool itself."

requirements-completed:
  - TOOL-01  # Register a Python callable as a tool with a JSON schema
  - TOOL-02  # Every tool invocation is logged with input, output, duration via ToolResult fields plus the optional on_log callback
  - TOOL-03  # At least one example tool ships: read_file

known-limitations:
  - "No multi-turn model loop. Calling execute_tool_uses returns to the caller; the caller is responsible for posting tool_results back to the model and continuing the conversation. Phase 07/08 will own this."
  - "read_file_tool is the only built-in. write_file, list_directory, search, shell, http_get all defer until specific phases need them."
  - "ToolResult.latency_ms uses perf_counter which is process-monotonic. Wall-clock latency drift across long-running tools is not captured."
  - "Logger callback is synchronous. Async tools and an async logger get bolted on when Phase 07 wires the async CLI path."

# Metrics
duration: 21m
completed: 2026-05-23
commit-count: 1
test-count: 23 (54 total cumulative)
lint-issues: 0
new-public-api-symbols: 4 (ToolRegistry, ToolResult, execute_tool_uses, read_file_tool)
