# Phase 13 Plan 02 Summary

**Status:** Shipped
**Commit:** feat(13): delegate_to_agent tool with shared budget and parallel fan-out
**Date:** 2026-05-23

## What shipped

The `delegate_to_agent` tool is now invocable from any coordinator. A
shared `IterationBudget` spans the whole delegation tree, the
`Conversation` classes on both providers honor a profile's
`system_prompt` on every turn, and multiple delegate calls in one
batch run concurrently.

### Conversation system prompt

`_anthropic.Conversation` and `_gemini.Conversation` both accept
`system_prompt` in `__init__` and apply it on every `send()`:

- Anthropic sends it via the `system` field on every `messages.create`
  request (the API requires it per turn, not just the first one).
- Gemini routes it through `GenerateContentConfig.system_instruction`
  via the existing `_build_config` kwargs path on every turn.

### run_agent_loop

`run_agent_loop` gained two optional kwargs with backward-compatible
defaults:

- `budget: IterationBudget | None = None`: when None, a fresh local
  budget of `max_iterations` is created so single-agent callers behave
  identically. When set, the loop drains the shared pool instead.
- `system_prompt: str | None = None`: forwarded to the provider's
  Conversation.

The iteration counter was replaced by `budget.consume()` so a
delegation tree shares one ceiling.

### make_delegate_tool

A closure factory in `tools/delegation.py` that captures `db`,
`master_registry`, `parent_trace_id`, `budget`, and `provider`. The
returned `Tool` has a tiny JSON schema (`agent_name`, `task`) and a
handler that:

1. Loads the named profile from the database (returns a safe error
   string if missing).
2. Filters the master registry by the profile's `allowed_tools`.
3. Calls `run_agent_loop` with the shared budget and the profile's
   system prompt.
4. Records the sub-agent trace with `parent_trace_id` and
   `agent_profile_name` so the dashboard can reconstruct the tree.
5. Returns the sub-agent's final text response.

The `from horus_os.agent import run_agent_loop` lives inside the
factory to break the agent <-> delegation import cycle.

### Parallel execute_tool_uses

`execute_tool_uses` now partitions `result.tool_uses` into delegate and
non-delegate calls. Non-delegate tools and lone delegate calls stay on
the sync path. Two or more delegate calls run through a bounded
`ThreadPoolExecutor(max_workers=len(delegate_uses))` with
`as_completed`. Results match back to requests by `tool_use_id`, so
completion-order outputs are correct for both providers.

## Files touched

- `src/horus_os/_providers/_anthropic.py`: `Conversation` system_prompt
- `src/horus_os/_providers/_gemini.py`: `Conversation` system_prompt
- `src/horus_os/agent.py`: `_new_conversation` and `run_agent_loop`
  extended; `IterationBudget` import
- `src/horus_os/tools/delegation.py`: `make_delegate_tool` factory
- `src/horus_os/tools/loop.py`: partitioned execution with parallel
  delegate fan-out, extracted `_execute_one`
- `tests/test_delegation.py`: 8 new integration tests

## Test count delta

| Surface | Before | After |
|---------|--------|-------|
| delegation | 10 | 17 (+7 integration tests; one additional helper test) |
| full suite | 200 | 208 |

All green: `python -m pytest -q` → 208 passed.

## Lint status

`ruff check .` and `ruff format --check .` clean.

## Phase 13 success criteria

- [x] `delegate_to_agent` registered and invocable from any profile
- [x] Sub-agent traces carry `parent_trace_id` linking to coordinator
- [x] 10-iteration cap applies across the whole tree via shared budget
- [x] Parallel delegation completes and merges results back

## Notable / deferred

- Sub-agents inherit `delegate_to_agent` when `allowed_tools=None`.
  Documented in `_filter_registry` and `make_delegate_tool` docstrings.
  Shared budget is the safety valve. `max_delegation_depth` deferred
  to v0.3 per `13-CONTEXT.md`.
- `run_agent_loop` does not write a trace itself. Top-level
  invocations (CLI, server) write the coordinator trace; the
  delegation handler writes sub-agent traces. The CLI/server layers
  pass their `trace_id` as `parent_trace_id` to `make_delegate_tool`
  when wiring the delegation tool into the master registry.
- Parallel result ordering is completion order, not request order.
  Both providers match by `tool_use_id`, so this is correct by design.
- Provider-per-profile deferred to v0.3; sub-agents inherit the
  coordinator's provider.
