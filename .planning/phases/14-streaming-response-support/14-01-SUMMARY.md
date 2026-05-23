# Phase 14 - Plan 01 Summary: Streaming Response Support

**Shipped:** 2026-05-23
**Plan:** 14-01-PLAN.md
**Requirement:** STREAM-01

## What shipped

`run_agent_stream`, an async generator that yields incremental text tokens
from both Anthropic and Gemini providers. Tool requests surfaced
mid-flight are emitted as `ToolCallEvent` values after the text stream
completes, so consumers can observe a tool ask without `run_agent_stream`
dispatching it. Tool execution stays in `run_agent_loop`. The change is
purely additive: `run_agent`, `run_agent_async`, and `run_agent_loop`
were not modified.

## Files touched

| File | Change |
|------|--------|
| `src/horus_os/types.py` | Added `ToolCallEvent` dataclass |
| `src/horus_os/_providers/_anthropic.py` | Added `stream_anthropic_async` |
| `src/horus_os/_providers/_gemini.py` | Added `stream_gemini_async` |
| `src/horus_os/agent.py` | Added `run_agent_stream` dispatcher |
| `src/horus_os/__init__.py` | Exported `run_agent_stream` and `ToolCallEvent` |
| `tests/test_provider_anthropic.py` | 4 new streaming tests |
| `tests/test_provider_gemini.py` | 5 new streaming tests |
| `tests/test_agent.py` | 7 new dispatcher and surface tests |

## Test count delta

- Pre Phase 14: 208 tests
- Post Phase 14: 224 tests (+16)
  - +4 Anthropic streaming
  - +5 Gemini streaming
  - +7 dispatcher and public-surface

All offline. The streaming SDKs (`anthropic.AsyncAnthropic`,
`google.genai.Client`) are monkeypatched via `sys.modules`, mirroring the
existing provider test pattern.

## Verification

- `pytest -x -q` -> 224 passed
- `ruff check .` -> clean
- `ruff format --check .` -> 51 files already formatted
- `python -c "from horus_os import run_agent_stream, ToolCallEvent"` -> ok

## Commits

1. `feat(14): provider async streaming helpers and ToolCallEvent type`
2. `feat(14): run_agent_stream dispatcher and public exports`
3. `docs(14): summary for plan 14-01`

## Design notes worth flagging

- **Trace recording is not in this phase.** `run_agent_stream` does not
  write to SQLite. Phase 15 (CLI) and Phase 16 (dashboard) are responsible
  for assembling yielded `str` chunks into the final response text and
  recording a single trace per call.
- **Anthropic system prompt placement.** The streaming helper passes
  `system` as a top-level field on `messages.stream(...)`, not as a
  message role; putting it in the messages list 400s the API.
- **Gemini heartbeat chunks.** Each chunk is gated with `if chunk.text:`
  because the SDK can emit usage-only or empty chunks.
- **ToolCallEvent emission ordering.** Anthropic events are read from the
  final assembled message after `text_stream` drains. Gemini events are
  buffered during streaming and yielded after the text loop. Both surface
  tool requests after text, so consumers see a consistent shape.

## Deferred

- **In-stream tool dispatch.** Out of scope by design. Streaming and tool
  use do not compose in a single pass without buffering, which negates the
  streaming win. Anyone needing tool execution should call
  `run_agent_loop`.
- **Structured StreamChunk wrapper type.** Phase 14 yields `str` and
  `ToolCallEvent` directly. A richer event type (e.g., delta + snapshot,
  usage events) can be layered on without breaking the current contract if
  Phase 15 or 16 needs it.
