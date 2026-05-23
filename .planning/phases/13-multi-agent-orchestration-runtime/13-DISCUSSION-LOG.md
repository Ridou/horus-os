# Phase 13 Discussion Log: Multi-agent orchestration runtime

**Date:** 2026-05-23
**Mode:** Headless auto-mode (no user present)
**Phase:** 13 - Multi-agent orchestration runtime

---

## Summary

Phase 13 has both a research document and two execution plans already in place. The context discussion identified five implementation gray areas and resolved each autonomously. All decisions align with the research recommendations and existing codebase patterns.

---

## Area 1: Budget threading in run_agent_loop

**Question:** Should `run_agent_loop` accept a pre-built `IterationBudget` object or just a `max_iterations: int`?

**Options considered:**
- A. Accept `budget: IterationBudget | None = None` alongside existing `max_iterations` - backward-compatible
- B. Replace `max_iterations` with a required `IterationBudget` parameter - breaks all existing callers
- C. Accept only `max_iterations: int` and create budget internally - cannot share budget across delegation tree

**Selected:** Option A

**Notes:** Research open question OQ-1 recommended this approach. Keeping `max_iterations` avoids touching the CLI, server, and test call sites. The coordinator passes a shared budget explicitly when building a delegation tree; leaf callers continue to pass nothing.

---

## Area 2: Unknown agent name handling

**Question:** Should `delegate_to_agent` raise an exception or return an error string when the profile is not found?

**Options considered:**
- A. Return error string `f"Error: agent profile {name!r} not found"` - consistent with execute_tool_uses
- B. Raise `ValueError` - caught by execute_tool_uses anyway, appears as ToolResult.error
- C. Return empty string - ambiguous, model cannot distinguish from a valid empty response

**Selected:** Option A

**Notes:** Research open question OQ-2 recommended this. The execute_tool_uses loop already captures all exceptions as ToolResult.error strings. Returning directly is cleaner and gives the coordinator model a human-readable error it can surface.

---

## Area 3: Sub-agent provider inheritance

**Question:** Should sub-agents use the same provider as the coordinator, or should the profile define a preferred provider?

**Options considered:**
- A. Sub-agents inherit coordinator provider; default_model overrides model only - no schema change needed
- B. Add `default_provider` field to AgentProfile - requires schema change on top of Phase 12
- C. Infer provider from model name string (e.g., "claude-" -> anthropic) - brittle

**Selected:** Option A

**Notes:** AgentProfile has no provider field (Phase 12 decision). Cross-provider delegation trees add billing and trace complexity not warranted for v0.2. Provider-per-profile is a clean v0.3 addition once usage patterns are known.

---

## Area 4: Parallel delegation result ordering

**Question:** Should parallel delegate results be returned in original tool_uses order or completion order?

**Options considered:**
- A. Completion order (as_completed) - natural ThreadPoolExecutor pattern, no overhead
- B. Re-sort by tool_use_id to match original order - extra complexity, no correctness benefit

**Selected:** Option A

**Notes:** Anthropic and Gemini APIs match tool results to requests via tool_use_id, not list position. No re-sorting needed.

---

## Area 5: Recursive delegation behavior

**Question:** Should sub-agents be allowed to delegate further, or should delegate_to_agent be excluded from sub-agent registries?

**Options considered:**
- A. Allow recursion; shared IterationBudget is safety valve; document as footgun
- B. Explicitly exclude delegate_to_agent from all sub-agent registries
- C. Add max_delegation_depth parameter to control depth explicitly

**Selected:** Option A

**Notes:** Option B would require special-casing in _filter_registry. Option C adds parameter threading complexity. The shared budget already prevents runaway recursion. This is a desktop tool used by the owner - deep delegation chains are unusual but not harmful. Documenting the behavior in delegation.py is sufficient for v0.2.

---

## Deferred Ideas

| Idea | Reason Deferred |
|------|----------------|
| Provider-per-AgentProfile | v0.3 scope; requires schema change and cross-provider trace correlation |
| max_delegation_depth param | Premature; budget already caps iterations; revisit if users hit unexpected depth |
| load_profile() result caching | Premature optimization for a desktop SQLite tool |
| Streaming sub-agent tokens to coordinator | Phase 14 (streaming) concern, not Phase 13 |

---

## Claude Discretion Items

| Item | Decision |
|------|----------|
| Keeping max_iterations alongside budget | Backward compatibility takes priority; no cleanup of existing call sites in Phase 13 |
| system_prompt on every Anthropic turn | Required by API; applied in Conversation.send() on all turns, not just the first |
| v3->v4 try/except pattern | ALTER TABLE not idempotent; wrap each column addition in try/except OperationalError |
