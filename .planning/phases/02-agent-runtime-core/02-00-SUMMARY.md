---
phase: 02-agent-runtime-core
plan: "00"
subsystem: agent-runtime
tags: [agent-runtime, anthropic, gemini, tool-use, dispatcher]

# Dependency graph
requires:
  - phase: "01-repo-scaffold-and-ci"
    provides: "Python package skeleton, ruff + pytest pipeline, CI matrix"
provides:
  - "Top-level `run_agent` and `run_agent_async` entry points in `horus_os.agent`"
  - "`Tool`, `ToolUse`, `AgentResult` data types in `horus_os.types`, re-exported from package root"
  - "`call_anthropic` / `call_anthropic_async` provider functions in `horus_os._providers._anthropic`"
  - "`call_gemini` / `call_gemini_async` provider functions in `horus_os._providers._gemini`"
  - "Lazy SDK imports so the package loads cleanly with zero optional deps"
  - "Optional dependency groups `[anthropic]`, `[gemini]`, `[all]` for selective installs"
affects:
  - "Phase 03 (persistence) will write AgentResult instances to SQLite traces"
  - "Phase 04 (tool registry) will register handlers and add the execute loop that consumes AgentResult.tool_uses"
  - "Phase 07 (CLI) will surface `run_agent` via `horus-os run <prompt>`"
  - "Phase 08 (web chat) will surface `run_agent_async` via a streaming endpoint"

# Tech tracking
tech-stack:
  added:
    - "anthropic>=0.40 (optional dep, [anthropic] extra)"
    - "google-genai>=0.3 (optional dep, [gemini] extra)"
    - "pytest-asyncio>=0.24 (dev dep, asyncio_mode=auto for async tests)"
  patterns:
    - "Lazy SDK imports inside call sites, not at module load. Keeps the import surface zero-dep and avoids partial-install errors."
    - "No abstraction layer above the SDKs; only normalization of the input Tool shape and output AgentResult shape."
    - "Mock SDKs via sys.modules injection in tests, no live API calls in CI."

key-files:
  created:
    - "src/horus_os/types.py, 42 lines, Tool + ToolUse + AgentResult dataclasses"
    - "src/horus_os/agent.py, 50 lines, dispatcher with provider validation"
    - "src/horus_os/_providers/__init__.py, empty marker"
    - "src/horus_os/_providers/_anthropic.py, 112 lines, sync + async Anthropic calls and response parsing"
    - "src/horus_os/_providers/_gemini.py, 133 lines, sync + async Gemini calls and response parsing"
    - "tests/test_agent.py, 91 lines, 7 dispatcher tests"
    - "tests/test_provider_anthropic.py, 124 lines, 4 mocked Anthropic tests"
    - "tests/test_provider_gemini.py, 187 lines, 5 mocked Gemini tests"
  modified:
    - "src/horus_os/__init__.py, re-exports the public API"
    - "pyproject.toml, optional-dependencies groups + pytest-asyncio dev dep + asyncio_mode=auto"

key-decisions:
  - "No provider abstraction layer above the SDKs. Provider modules use each SDK directly. The only shared shape is Tool (input normalization) and AgentResult (output normalization). This matches the v0.1 architecture decision recorded in PROJECT.md."
  - "Lazy SDK imports inside the call functions. A user can `pip install horus-os[anthropic]` without ever needing google-genai on disk, and vice versa. The package itself has zero hard third-party dependencies."
  - "GEMINI_API_KEY is read first, GOOGLE_API_KEY is the fallback alias. Both are documented; GEMINI_API_KEY is preferred because it makes the intent explicit and avoids collisions with other Google API uses."
  - "Default models are pinned: claude-sonnet-4-6 (Anthropic) and gemini-2.5-flash (Gemini). Both are overridable per call via the `model` kwarg. These match the current most-capable production tier as of the runtime cut date."
  - "AgentResult.tool_uses captures the model's intent, but Phase 02 does NOT auto-invoke handlers. The execute-loop lives in Phase 04 alongside the registry. This keeps the Phase 02 surface focused and lets us ship the runtime before the registry pattern is finalized."
  - "Test mocking uses sys.modules injection rather than installing the real SDKs. CI does not need network or API keys. Real SDKs install via the [anthropic] / [gemini] extras when a real user runs the code."

patterns-established:
  - "Provider modules live in `_providers/` (private package). External callers go through `horus_os.agent.run_agent`, not the provider modules directly. This insulates the runtime from any provider-specific shape."
  - "Sync + async siblings: every provider exposes both `call_<provider>` and `call_<provider>_async`. The dispatcher picks the right one based on which entry point was called."
  - "All test fakes are local dataclass-like objects that mimic the SDK shape only as far as our parser reads. No need to mirror the full SDK surface."

requirements-completed:
  - AGENT-01  # Contract for at least one registered tool, the Tool type is shipped. Auto-invocation lands in Phase 04.
  - AGENT-02  # Every agent run produces a structured AgentResult containing text + tool_uses + usage.
  - AGENT-03  # Both Anthropic and Gemini SDKs supported via separate provider modules.
  - CORE-05  # User-supplied API keys honored: ANTHROPIC_API_KEY for Anthropic, GEMINI_API_KEY (or GOOGLE_API_KEY) for Gemini.

known-limitations:
  - "No tool execution loop. AgentResult.tool_uses is captured but Tool.handler is never invoked automatically. Phase 04 closes this."
  - "No persistence. AgentResult is returned to the caller and lost afterward. Phase 03 will add SQLite trace storage."
  - "No streaming. Both providers support streaming but Phase 02 returns the full response synchronously. Streaming surfaces in Phase 07 (CLI) and Phase 08 (web chat) where it actually matters."
  - "No retry, no rate-limit handling, no cost tracking. v0.5 (Observability) handles cost tracking. Retry semantics defer to the SDKs themselves for now."

# Metrics
duration: 22m
completed: 2026-05-23
commit-count: 1
test-count: 16 (19 total with Phase 01 carryover)
lint-issues: 0
new-public-api-symbols: 5 (run_agent, run_agent_async, Tool, ToolUse, AgentResult)
