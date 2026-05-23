---
phase: 07-cli-surface
plan: "01"
subsystem: agent-loop-and-cli
tags: [cli, multi-turn-loop, conversation, tool-execution, run-subcommand]

# Dependency graph
requires:
  - phase: "02-agent-runtime-core"
    provides: "Tool, ToolUse, AgentResult, provider modules"
  - phase: "04-tool-registry"
    provides: "ToolRegistry, execute_tool_uses, read_file_tool"
  - phase: "05-memory-layer-read-path"
    provides: "NotesStore, read-side notes tools"
  - phase: "06-memory-layer-write-path"
    provides: "NotesStore writes, Database.record_note_write"
  - phase: "07-00"
    provides: "Config, CLI scaffold, init and traces subcommands"
provides:
  - "run_agent_loop function in horus_os.agent"
  - "Conversation class in horus_os._providers._anthropic"
  - "Conversation class in horus_os._providers._gemini"
  - "horus-os run subcommand with default tool registry and audit-trail wiring"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Provider-owned message history. Each Conversation holds its own native message list and translates Tool/ToolResult at the boundary. No abstraction layer."
    - "Loop separation. run_agent_loop orchestrates send -> execute -> send; it never touches raw SDK shapes."
    - "Default registry composition. The CLI builds the full v0.1 tool set (read_file sandboxed to notes_dir, plus the five memory tools) in one helper function so future surfaces can reuse it."
    - "on_write callback wired to Database.record_note_write so every model-driven write lands in the audit table without coupling NotesStore to the storage layer."

key-files:
  created:
    - "src/horus_os/cli/run_cmd.py, 127 lines, run subcommand handler"
    - "tests/test_agent_loop.py, 137 lines, 8 tests"
    - "tests/test_conversation_anthropic.py, 130 lines, 6 tests"
    - "tests/test_conversation_gemini.py, 174 lines, 6 tests"
    - "tests/test_cli_run.py, 170 lines, 8 tests"
  modified:
    - "src/horus_os/agent.py, added run_agent_loop function"
    - "src/horus_os/_providers/_anthropic.py, added Conversation class"
    - "src/horus_os/_providers/_gemini.py, added Conversation class"
    - "src/horus_os/cli/__init__.py, re-exports run_run"
    - "src/horus_os/__main__.py, wires the run subcommand"
    - "src/horus_os/__init__.py, re-exports run_agent_loop"

key-decisions:
  - "Conversation as a class per provider rather than a stateless function with an explicit history kwarg. The class encapsulates the native history shape, and tests confirm the protocol on each provider independently."
  - "Provider state lives in the Conversation, not in run_agent_loop. The loop is a thin orchestrator that asks each Conversation to take the next step. A future async loop or streaming variant can wrap the same Conversation instance."
  - "Handler exceptions are sent back to the model. The model can decide to retry, give up, or apologize. The alternative (abort the loop on any tool error) blocks legitimate uses where a tool transiently fails."
  - "Default registry is built per-run, not cached. Each run gets a fresh NotesStore + on_write hook bound to the freshly-opened Database. Cheap, no shared mutable state between runs."
  - "argparse choices for --provider. We accept the SystemExit(2) behavior because it gives a clean usage error. The test wraps the call in pytest.raises(SystemExit) to confirm the exit code."

patterns-established:
  - "Lazy Conversation construction. The provider SDK import happens in __init__ so a user without that SDK installed still gets a clear ImportError at the point of use rather than at horus-os startup."
  - "Tool result transport. Anthropic uses content blocks with type=tool_result and an optional is_error flag. Gemini uses function_response parts with a response dict. Both Conversations translate ToolResult.error vs ToolResult.output into the right shape per provider."
  - "Per-run trace recording. The CLI always records a trace, success or failure, unless --no-record is set. Failure mode includes the exception type and message in error_message so the dashboard can render the actual problem."

requirements-completed:
  - CORE-02  # CLI accepts prompts and returns structured results
  - AGENT-01 # Full multi-turn tool execution: registry + loop + handler invocation
  # AGENT-02 was completed in 03-00 with the storage primitive; the CLI now exercises the full
  # path end-to-end (run_agent_loop -> Database.record_trace -> Database.list_traces).

known-limitations:
  - "Streaming is not wired. The CLI prints the full response once the loop terminates. Live token streaming defers to a later phase when the dashboard renders it visually."
  - "Async path through the loop is not exposed at the CLI. run_agent_async exists from 02-00 but run_agent_loop is sync only. An async loop variant lands when Phase 08 (web chat) needs it for streaming."
  - "The default tool registry is hard-coded in run_cmd. A future phase can read tool selections from config to let users opt into or out of specific tools."
  - "No context window management. Long conversations will fail when they exceed the provider's input limit. Compaction lands in a later phase."

# Metrics
duration: 38m
completed: 2026-05-23
commit-count: 1
test-count: 28 (148 total cumulative)
lint-issues: 0
new-public-api-symbols: 1 (run_agent_loop)
new-cli-subcommands: 1 (run)
