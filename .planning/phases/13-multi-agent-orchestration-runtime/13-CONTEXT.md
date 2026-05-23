# Phase 13 Context: Multi-agent orchestration runtime

**Date:** 2026-05-23
**Phase:** 13
**Status:** Context captured (headless auto-mode)

---

## Domain

Phase 13 delivers the `delegate_to_agent` tool, which lets a coordinator agent invoke named sub-agents by profile name. Sub-agent traces link back to the coordinator via a `parent_trace_id` column added in a v3->v4 schema migration. A thread-safe `IterationBudget` object is shared across the entire delegation tree so the coordinator and all sub-agents draw from one pool. This phase gates Phases 15 (CLI surface), 16 (dashboard), and downstream delegation consumers.

The codebase already has all required primitives: `agent_profiles` table (Phase 12), `run_agent_loop` for multi-turn execution, `ToolRegistry` for tool dispatch, and `execute_tool_uses` for batch tool execution. Phase 13 wires these together with minimal new surface area.

---

## Canonical Refs

- `.planning/ROADMAP.md` - Phase 13 success criteria and dependency chain (gates 15, 16, 17)
- `.planning/REQUIREMENTS.md` - MA-02, MA-03, MIG-01
- `src/horus_os/storage.py` - Database class to extend with v4 schema, record_trace, list_child_traces
- `src/horus_os/agent.py` - run_agent_loop to extend with budget and system_prompt params
- `src/horus_os/tools/loop.py` - execute_tool_uses to extend with parallel delegate execution
- `src/horus_os/_providers/_anthropic.py` - Conversation to extend with system_prompt support
- `src/horus_os/_providers/_gemini.py` - Conversation to extend with system_prompt support
- `src/horus_os/types.py` - AgentProfile dataclass (Phase 12 output, consumed by Phase 13)
- `.planning/phases/13-multi-agent-orchestration-runtime/13-RESEARCH.md` - Full architecture, patterns, and pitfall log

---

## Decisions

### 1. Budget threading in run_agent_loop

**Decision:** Add `budget: IterationBudget | None = None` to `run_agent_loop`. Keep `max_iterations: int = 10` for backward compatibility. When `budget` is None, create a local `IterationBudget(max_iterations)`. When `budget` is provided, use it directly and ignore `max_iterations`.

```python
def run_agent_loop(
    prompt: str,
    *,
    registry: ToolRegistry,
    provider: str = "anthropic",
    model: str | None = None,
    max_iterations: int = 10,
    budget: IterationBudget | None = None,
    system_prompt: str | None = None,
    on_tool_result: Callable[[ToolResult], None] | None = None,
) -> AgentResult:
    _budget = budget if budget is not None else IterationBudget(max_iterations)
    while result.tool_uses:
        if not _budget.consume():
            break
        ...
```

**Why:** All existing callers (`horus-os run`, CLI tests, server) call `run_agent_loop(prompt, registry=reg)` with no budget arg. Adding `budget` as optional leaves those call sites unchanged. Passing an explicit budget enables cross-agent tree-level cap sharing for delegation chains.

### 2. Unknown agent name handling in delegate_to_agent

**Decision:** Return an error string, not raise. Specifically: `f"Error: agent profile {agent_name!r} not found"`.

**Why:** `execute_tool_uses` already captures all handler exceptions as error strings in `ToolResult.error`. The delegation handler should be consistent with that pattern. Returning an error string gives the coordinator model a chance to surface the error or recover. Raising would bubble up through `execute_tool_uses` and be caught as a generic exception anyway - returning directly is cleaner.

### 3. Sub-agent provider inheritance

**Decision:** Sub-agents use the same provider as the coordinator. The `AgentProfile.default_model` overrides the model only, not the provider. `make_delegate_tool` captures `provider` at factory creation time and passes it through to every `run_agent_loop` call it makes.

**Why:** `AgentProfile` has no `default_provider` field (Phase 12 decision). Adding provider-per-profile is v0.3 scope. A delegation tree mixing providers (e.g., coordinator on Anthropic, sub-agent on Gemini) would require cross-provider trace correlation and billing complexity - not warranted for a v0.2 desktop tool. Any coordinator that switches provider does so at the top-level call; all sub-agents follow.

### 4. Parallel delegation result ordering

**Decision:** Return results in completion order (`as_completed`), not in the original `tool_uses` order. No re-sorting after parallel execution.

**Why:** The Anthropic and Gemini APIs match tool results to requests via `tool_use_id`, not by list position. Re-sorting the results to match the original order adds complexity for zero correctness benefit. `ThreadPoolExecutor` with `as_completed` is the natural pattern and yields results in whichever order they finish.

### 5. Recursive delegation (sub-agents delegating to other sub-agents)

**Decision:** Allow recursive delegation when `allowed_tools=None`. Do not explicitly exclude `delegate_to_agent` from sub-agent registries. The shared `IterationBudget` is the only safety valve; no `max_depth` parameter is added.

**Why:** Adding `max_depth` would require threading another parameter through `make_delegate_tool` and `run_agent_loop`. The shared budget already prevents infinite loops by design. This is a personal desktop tool used by the owner - unexpected deep delegation is annoying but not a security issue. Document the footgun in `delegation.py`. For v0.3+, consider adding `max_delegation_depth` if users hit it in practice.

---

## Implementation Notes

### Execution plan

- **Plan 01** (wave 1): Extend `storage.py` with v3->v4 migration (`parent_trace_id`, `agent_profile_name` columns + index), extend `record_trace` signature, add `list_child_traces`. Create `tools/delegation.py` with `IterationBudget` and `_filter_registry`. Tests in `test_storage.py` and new `test_delegation.py`.
- **Plan 02** (wave 2, depends on Plan 01): Add `system_prompt` to both `Conversation` classes. Extend `run_agent_loop` with `budget` and `system_prompt`. Add `make_delegate_tool` factory to `delegation.py`. Add parallel `delegate_to_agent` path to `loop.py`. Delegation integration tests in `test_delegation.py`.

### Key pitfalls (from research)

- Budget must be created once and passed by reference down the tree - never created inside threads
- `system_prompt` must be included in EVERY `messages.create` call (Anthropic requires it on every turn)
- v3->v4 ALTER TABLE is not idempotent; wrap in `try/except sqlite3.OperationalError`
- `allowed_tools=None` passes `delegate_to_agent` through to sub-agents - documented behavior

---

## Deferred Ideas

- Provider-per-AgentProfile (sub-agent on different LLM than coordinator) - v0.3
- `max_delegation_depth` parameter to limit recursive delegation depth - v0.3 if users hit it
- Cache `load_profile()` within a delegation run to avoid repeated SQLite reads - premature for desktop
- Delegation result streaming (pipe sub-agent tokens to coordinator in real time) - Phase 14 concern

---

## Gray Areas Decided Autonomously

This context was captured in headless auto-mode. The following areas were identified and decided without user input:

| Area | Decision |
|------|----------|
| Budget threading | budget: IterationBudget | None = None; keep max_iterations for backward compat |
| Unknown agent name | Return error string, not raise; consistent with execute_tool_uses pattern |
| Sub-agent provider | Inherits coordinator provider; default_model overrides model only |
| Parallel result ordering | Completion order (as_completed); no re-sort needed (tool_use_id is the key) |
| Recursive delegation | Allowed when allowed_tools=None; shared budget is safety valve; no max_depth |
