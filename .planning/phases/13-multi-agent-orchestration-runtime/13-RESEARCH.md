# Phase 13: Multi-Agent Orchestration Runtime - Research

**Researched:** 2026-05-23
**Domain:** Multi-agent orchestration, Python runtime, SQLite schema migration
**Confidence:** HIGH

## Summary

Phase 13 adds coordinator-to-sub-agent delegation to the horus-os runtime. A new `delegate_to_agent` tool (registered like any other tool) lets a coordinator agent invoke named sub-agents by profile name. Sub-agent traces link back to the coordinator's trace via a `parent_trace_id` column added in a v3->v4 schema migration.

The codebase already has everything needed as foundation: `agent_profiles` table (Phase 12), `run_agent_loop` for multi-turn execution, `ToolRegistry` for tool dispatch, and `execute_tool_uses` for batch tool execution. Phase 13 wires these together with minimal new surface area.

The iteration budget requirement ("applies to the whole tree") is the key design constraint. A shared `IterationBudget` object (a lock-protected counter) threads through the delegation chain so the coordinator and all sub-agents share one pool.

**Primary recommendation:** Implement delegation as a tool factory that closes over a `Database`, a master `ToolRegistry`, and a shared `IterationBudget`. No new abstractions beyond what Phase 13 strictly requires.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Agent profile lookup | Database/Storage | - | Profile data lives in SQLite; delegation tool queries it at call time |
| Sub-agent execution | Agent runtime (`agent.py`) | - | `run_agent_loop` is the canonical executor; sub-agents reuse it |
| Iteration budget tracking | Shared counter in orchestration layer | - | Budget spans coordinator + sub-agents; must be a shared mutable object |
| Trace parent/child linkage | Database/Storage | Agent runtime | `record_trace` writes the link; runtime passes the ID |
| Parallel delegation | Tool execution (`loop.py`) | Standard library `concurrent.futures` | Multiple `delegate_to_agent` calls in one response batch run via `ThreadPoolExecutor` |
| Sub-agent tool scoping | `ToolRegistry` filter | Orchestration layer | `allowed_tools` from profile filters the master registry at delegation time |

## Standard Stack

### Core (no new dependencies required)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `concurrent.futures` | 3.11+ | Parallel sub-agent calls via `ThreadPoolExecutor` | Ships with Python, avoids adding `asyncio` complexity to the sync path |
| Python stdlib `threading` | 3.11+ | `Lock` for shared `IterationBudget` counter | Thread-safe without external deps |
| SQLite `ALTER TABLE ... ADD COLUMN` | 3.45 (installed) | v3->v4 schema migration | Additive-only migration, safe on existing databases |

**No new packages to install.** All required capabilities are in the Python standard library and existing project dependencies.

[VERIFIED: codebase inspection] - existing `agent.py`, `storage.py`, `tools/registry.py`, and `tools/loop.py` provide all primitives needed.

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `uuid` (stdlib) | 3.11+ | Generate trace IDs for sub-agent runs | Already used in `storage.py` |
| `time` (stdlib) | 3.11+ | Latency measurement for delegation | Already used in `tools/loop.py` |

**Installation:**

No new packages required.

## Architecture Patterns

### System Architecture Diagram

```
Coordinator prompt
        |
        v
run_agent_loop(budget=B, parent_trace_id=None)
        |
        +-- Anthropic/Gemini Conversation
        |         (system_prompt=coordinator_profile.system_prompt)
        |
        +-- execute_tool_uses(registry with delegate_to_agent)
                  |
                  +-- [if single delegate call] run synchronously
                  |
                  +-- [if multiple delegate calls] ThreadPoolExecutor
                           |
                           v
               delegate_to_agent(agent_name, task)
                           |
                           +-- db.load_profile(agent_name)
                           +-- build sub_registry (filtered by allowed_tools)
                           +-- budget.consume(1)  <-- shared budget
                           |
                           v
               run_agent_loop(budget=budget, parent_trace_id=coordinator_trace_id)
                           |
                           +-- Conversation(system_prompt=sub_agent_profile.system_prompt)
                           +-- execute_tool_uses(sub_registry)
                           |
                           v
               db.record_trace(..., parent_trace_id=coordinator_trace_id)
                           |
                           v
               return sub_agent result text
```

### Recommended Project Structure

No new top-level modules. Changes are localized to:

```
src/horus_os/
├── agent.py           # add system_prompt + parent_trace_id + budget params to run_agent_loop
├── storage.py         # schema v4 migration, record_trace new params
├── tools/
│   ├── loop.py        # parallel execution for multiple delegate calls
│   └── delegation.py  # NEW: make_delegate_tool factory + IterationBudget
├── types.py           # no changes needed (AgentResult, AgentProfile already exist)
└── _providers/
    ├── _anthropic.py  # Conversation: add system_prompt to __init__
    └── _gemini.py     # Conversation: add system_prompt to __init__
tests/
└── test_delegation.py # NEW: delegation tool, trace linkage, budget exhaustion
```

### Pattern 1: Shared Iteration Budget

**What:** A lock-protected counter shared across coordinator and all sub-agents in one tree.
**When to use:** Every `run_agent_loop` call in a multi-agent tree receives the same `IterationBudget` instance.

```python
# Source: [ASSUMED] - standard Python threading pattern
import threading

class IterationBudget:
    """Thread-safe iteration counter shared across a delegation tree."""

    def __init__(self, max_iterations: int) -> None:
        self._remaining = max_iterations
        self._lock = threading.Lock()

    def consume(self) -> bool:
        """Decrement by 1. Returns True if budget was available."""
        with self._lock:
            if self._remaining <= 0:
                return False
            self._remaining -= 1
            return True

    @property
    def remaining(self) -> int:
        with self._lock:
            return self._remaining
```

### Pattern 2: Delegate Tool Factory

**What:** A closure that captures database, master registry, parent trace ID, and budget. Returns a `Tool` with a `delegate_to_agent` handler.
**When to use:** Created once at the start of each `run_agent_loop` call for agents that have delegation capability.

```python
# Source: [ASSUMED] - closure-based tool factory matching existing tool patterns in builtin.py
from horus_os.tools.registry import ToolRegistry
from horus_os.types import Tool, AgentProfile

def make_delegate_tool(
    *,
    db: "Database",
    master_registry: ToolRegistry,
    parent_trace_id: str,
    budget: IterationBudget,
    provider: str = "anthropic",
) -> Tool:
    def _delegate(agent_name: str, task: str) -> str:
        profile = db.load_profile(agent_name)
        if profile is None:
            return f"Error: agent profile {agent_name!r} not found"
        sub_registry = _filter_registry(master_registry, profile.allowed_tools)
        result = run_agent_loop(
            task,
            registry=sub_registry,
            provider=provider,
            model=profile.default_model,
            budget=budget,
            system_prompt=profile.system_prompt or "",
            parent_trace_id=parent_trace_id,
        )
        return result.text

    return Tool(
        name="delegate_to_agent",
        description=(
            "Delegate a subtask to a named sub-agent. "
            "Returns the sub-agent's final text response."
        ),
        parameters={
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Name of the agent profile to delegate to.",
                },
                "task": {
                    "type": "string",
                    "description": "The task or question to send to the sub-agent.",
                },
            },
            "required": ["agent_name", "task"],
        },
        handler=_delegate,
    )
```

### Pattern 3: Sub-Registry Filtering

**What:** Filter the master registry to only tools listed in `allowed_tools`. `None` means unrestricted - pass the full master registry.
**When to use:** Always, when building the registry for a sub-agent invocation.

```python
# Source: [ASSUMED] based on AgentProfile.allowed_tools semantics from Phase 12
def _filter_registry(
    master: ToolRegistry,
    allowed_tools: list[str] | None,
) -> ToolRegistry:
    if allowed_tools is None:
        return master  # unrestricted - reuse master directly
    filtered = ToolRegistry()
    for name in allowed_tools:
        tool = master.get(name)
        if tool is not None:
            filtered.register(tool)
    return filtered
```

### Pattern 4: System Prompt Support in Conversation

**What:** Add `system_prompt` parameter to both `Conversation.__init__` methods.
**When to use:** Sub-agent conversations are initialized with the profile's system prompt.

For Anthropic:
```python
# Source: Anthropic API docs - system param on messages.create
class Conversation:
    def __init__(self, *, model: str | None = None, system_prompt: str | None = None) -> None:
        ...
        self._system_prompt = system_prompt or ""
    
    def send(self, ...) -> AgentResult:
        request: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": self._messages,
        }
        if self._system_prompt:
            request["system"] = self._system_prompt
        ...
```

For Gemini:
```python
# Source: Gemini API - system_instruction in GenerateContentConfig
def _build_config(tools, kwargs):
    ...
    # system_instruction already handled via kwargs passthrough in existing _build_config
    # For Conversation class, pass system_prompt as system_instruction in config
```

### Pattern 5: Parallel Delegate Execution

**What:** When `execute_tool_uses` encounters multiple `delegate_to_agent` calls in one response, run them in parallel using `ThreadPoolExecutor`.
**When to use:** Only when there are 2+ `delegate_to_agent` calls in a single batch; fall back to sequential for single calls or non-delegate tools.

```python
# Source: [ASSUMED] - standard Python concurrent.futures pattern
from concurrent.futures import ThreadPoolExecutor, as_completed

def execute_tool_uses(registry, result, *, on_log=None):
    delegate_uses = [u for u in result.tool_uses if u.name == "delegate_to_agent"]
    other_uses = [u for u in result.tool_uses if u.name != "delegate_to_agent"]
    
    outcomes: list[ToolResult] = []
    
    # Non-delegate tools run sequentially (existing behavior)
    for use in other_uses:
        outcomes.append(_execute_one(registry, use, on_log=on_log))
    
    # Multiple delegate calls run in parallel
    if len(delegate_uses) > 1:
        with ThreadPoolExecutor(max_workers=len(delegate_uses)) as pool:
            futures = {pool.submit(_execute_one, registry, u, on_log=on_log): u for u in delegate_uses}
            for future in as_completed(futures):
                outcomes.append(future.result())
    elif delegate_uses:
        outcomes.append(_execute_one(registry, delegate_uses[0], on_log=on_log))
    
    return outcomes
```

### Pattern 6: Schema v3 -> v4 Migration

**What:** Additive ALTER TABLE to add `parent_trace_id` and `agent_profile_name` columns.
**When to use:** Applied in `Database.init()` as part of the existing idempotent migration chain.

```sql
-- Safe: SQLite ALTER TABLE ADD COLUMN never fails if column already exists (with IF NOT EXISTS check in Python)
ALTER TABLE traces ADD COLUMN parent_trace_id TEXT;
ALTER TABLE traces ADD COLUMN agent_profile_name TEXT;
CREATE INDEX IF NOT EXISTS idx_traces_parent_trace_id ON traces(parent_trace_id);
```

[VERIFIED: codebase inspection] - existing migration pattern in `storage.py` uses version check + ALTER TABLE. The same approach works for v4.

### Anti-Patterns to Avoid

- **Passing `ToolRegistry` as a serializable tool input:** Registries are Python objects, not JSON-serializable. The delegation handler must close over the registry as a Python variable, not pass it through the tool JSON schema.
- **Creating a new `Database` connection per sub-agent call:** Expensive and unnecessary. Pass the same `Database` instance down the delegation chain.
- **Infinite delegation depth without budget enforcement:** Without the shared `IterationBudget`, a sub-agent could delegate to another sub-agent indefinitely. Always consume from the shared budget before recursing.
- **Re-registering `delegate_to_agent` in sub-agent registries when `allowed_tools` is None:** If `allowed_tools` is `None` (unrestricted) and the master registry includes `delegate_to_agent`, sub-agents will inherit delegation capability. This is intentional for v0.2 but worth documenting as a footgun.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Thread-safe counter | Custom atomic integer | `threading.Lock` + `int` | Simple, correct, no deps |
| Parallel execution | asyncio event loop for sync path | `ThreadPoolExecutor` | Sync path stays sync; no event loop needed |
| Agent profile lookup | Cache layer | Direct `db.load_profile()` per call | SQLite reads are fast enough for desktop use; premature optimization |
| Tool schema validation | Custom JSON Schema validator | Trust that model sends valid input (matches existing `execute_tool_uses` pattern) | Consistent with existing tool dispatch; add validation only at system boundary |

**Key insight:** Multi-agent orchestration in this codebase is "just another tool." The complexity lives in state threading (trace IDs, budget), not in new abstractions.

## Runtime State Inventory

> This section is N/A for Phase 13 - this is a greenfield feature addition, not a rename/refactor/migration. No existing runtime state uses "delegate_to_agent" or "parent_trace_id" strings.

**Nothing found in any category** - verified by codebase inspection. Phase 13 only adds new columns (v3->v4 migration) and new tools; it does not rename or remove any existing identifiers.

## Common Pitfalls

### Pitfall 1: Budget Not Shared Across Thread Boundaries

**What goes wrong:** Each `ThreadPoolExecutor` worker creates its own budget, so parallel sub-agents each get the full iteration count.
**Why it happens:** Budget object created inside the thread instead of being passed in.
**How to avoid:** Create `IterationBudget` once at the top-level `run_agent_loop` call; pass it by reference (Python object reference semantics) through all calls.
**Warning signs:** Tests show sub-agents each using up to `max_iterations` iterations independently.

### Pitfall 2: Missing `parent_trace_id` on Sub-Agent Traces

**What goes wrong:** Sub-agent trace is recorded without the coordinator's trace ID, breaking the parent/child link.
**Why it happens:** `record_trace` is called inside the sub-agent's loop without awareness of the coordinator context.
**How to avoid:** Pass `parent_trace_id` as a parameter through `run_agent_loop` down to the `record_trace` call. Keep it optional (defaults to `None`) so existing call sites don't break.
**Warning signs:** `SELECT * FROM traces WHERE parent_trace_id IS NOT NULL` returns 0 rows after a delegation run.

### Pitfall 3: `allowed_tools=None` Passes `delegate_to_agent` to Sub-Agents

**What goes wrong:** Sub-agents can recursively delegate, creating delegation trees deeper than expected.
**Why it happens:** `None` means unrestricted, so the master registry (which includes `delegate_to_agent`) is passed through entirely.
**How to avoid:** Document the behavior. For v0.2, this is acceptable. If needed, explicitly exclude `delegate_to_agent` from sub-agent registries when building filtered registries.
**Warning signs:** Stack depth grows unexpectedly in integration tests.

### Pitfall 4: SQLite `ALTER TABLE` Fails on v4 Re-Apply

**What goes wrong:** Running `Database.init()` twice on a v4 database raises `OperationalError: duplicate column name`.
**Why it happens:** `ALTER TABLE ... ADD COLUMN` is not idempotent unlike `CREATE TABLE IF NOT EXISTS`.
**How to avoid:** Wrap `ALTER TABLE` calls in a `try/except OperationalError` or check `SCHEMA_VERSION` before applying. Existing migration pattern in `storage.py` uses version check - continue that pattern.
**Warning signs:** `database.init()` fails on an existing v0.2 database.

### Pitfall 5: Conversation `system_prompt` Not Applied to Tool Result Turns

**What goes wrong:** System prompt is set on the first turn but lost on subsequent tool-result turns.
**Why it happens:** Anthropic `system` param must be sent on every `messages.create` call, not just the first.
**How to avoid:** Store `system_prompt` on the `Conversation` object and include it in the `request` dict on every `send()` call.
**Warning signs:** Sub-agent behavior changes between turn 1 (with system prompt) and turns 2+ (without).

## Code Examples

### Full `record_trace` signature after v4 update

```python
# Source: [ASSUMED] - extends existing signature in storage.py:record_trace
def record_trace(
    self,
    prompt: str,
    result: AgentResult,
    *,
    parent_trace_id: str | None = None,
    agent_profile_name: str | None = None,
    latency_ms: int | None = None,
    status: str = "success",
    error_message: str | None = None,
) -> str:
```

### `run_agent_loop` signature after Phase 13 update

```python
# Source: [ASSUMED] - extends existing signature in agent.py
def run_agent_loop(
    prompt: str,
    *,
    registry: ToolRegistry,
    provider: str = "anthropic",
    model: str | None = None,
    budget: IterationBudget | None = None,
    system_prompt: str | None = None,
    parent_trace_id: str | None = None,
    on_tool_result: Callable[[ToolResult], None] | None = None,
) -> AgentResult:
    # If no budget provided, create a local one (backwards-compatible)
    if budget is None:
        budget = IterationBudget(10)  # default max_iterations
    ...
```

### Verifying parent/child linkage in tests

```python
# Source: [ASSUMED] - follows existing test patterns in test_storage.py
def test_delegation_creates_child_trace(tmp_path):
    db = Database(tmp_path / "test.db")
    db.init()
    parent_id = db.record_trace("parent prompt", _make_result())
    child_id = db.record_trace(
        "child task",
        _make_result(),
        parent_trace_id=parent_id,
        agent_profile_name="summarizer",
    )
    child = db.get_trace(child_id)
    assert child.parent_trace_id == parent_id
    assert child.agent_profile_name == "summarizer"
    
    children = db.list_child_traces(parent_id)
    assert len(children) == 1
    assert children[0].trace_id == child_id
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single agent answers per request (v0.1) | Coordinator delegates to named sub-agents (v0.2) | Phase 13 | Enables task decomposition and specialization |
| Flat trace log | Parent/child linked trace tree | Phase 13 | Dashboard can show delegation hierarchies (Phase 16) |
| `max_iterations` per agent | Shared `IterationBudget` across tree | Phase 13 | Prevents runaway delegation chains |
| `Conversation` without system prompt | `Conversation(system_prompt=...)` | Phase 13 | Sub-agents honor their profile's instruction |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ThreadPoolExecutor` is sufficient for parallel delegation - no `asyncio` needed for sync path | Architecture Patterns | If async path needs parallel delegation too, `asyncio.gather` is required; revisit in Phase 14 (streaming) |
| A2 | Excluding `delegate_to_agent` from sub-agent `allowed_tools` filtering (when `None`) is acceptable for v0.2 | Pitfall 3 | Unexpected recursion depth; easy to fix post-v0.2 |
| A3 | `list_child_traces(parent_trace_id)` is a useful new query method on `Database` | Code Examples | Not strictly required if dashboard builds tree client-side; low risk |
| A4 | System prompt goes in Anthropic `system` param (not first user message) | Pattern 4 | Would produce incorrect behavior; HIGH confidence this is correct per Anthropic API docs |

## Open Questions

1. **Should `run_agent_loop` accept a pre-built `IterationBudget` or a plain `max_iterations: int`?**
   - What we know: budget sharing requires a mutable object; plain int is backwards-compatible
   - What's unclear: whether callers (CLI, dashboard, tests) need to provide a budget or just inherit a default
   - Recommendation: Accept `budget: IterationBudget | None = None`; create a default if not provided. Callers that want tree-budget control can pass one explicitly.

2. **Should `delegate_to_agent` silently ignore unknown agent names or raise?**
   - What we know: returning an error string is consistent with `execute_tool_uses` error handling
   - What's unclear: whether the coordinator model recovers gracefully from an error string vs. an exception
   - Recommendation: Return an error string (not raise). Consistent with existing `execute_tool_uses` error capture pattern.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All runtime code | Yes | 3.12.7 | - |
| SQLite | Storage layer | Yes | 3.45.3 | - |
| `concurrent.futures` | Parallel delegation | Yes | stdlib | - |
| `threading` | IterationBudget lock | Yes | stdlib | - |
| `anthropic` SDK | Anthropic provider | Yes (installed via dev deps) | - | - |
| `google-genai` SDK | Gemini provider | Yes (installed via dev deps) | - | - |

**No missing dependencies.** Phase 13 requires nothing beyond what is already installed.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `python -m pytest tests/test_delegation.py -x -q` |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MA-02 | Coordinator can delegate to a sub-agent via `delegate_to_agent` tool | unit | `pytest tests/test_delegation.py::test_delegate_tool_invokes_sub_agent -x` | Wave 0 |
| MA-02 | Parallel delegation: multiple delegate calls in one batch run concurrently | unit | `pytest tests/test_delegation.py::test_parallel_delegation -x` | Wave 0 |
| MA-02 | Sub-agent uses filtered tool registry based on `allowed_tools` | unit | `pytest tests/test_delegation.py::test_subagent_tool_scoping -x` | Wave 0 |
| MA-03 | Sub-agent trace has correct `parent_trace_id` | unit | `pytest tests/test_delegation.py::test_delegation_trace_linkage -x` | Wave 0 |
| MA-03 | `list_child_traces` returns all direct children of a trace | unit | `pytest tests/test_delegation.py::test_list_child_traces -x` | Wave 0 |
| MIG-01 | v3 database upgrades to v4 with new columns populated as NULL | unit | `pytest tests/test_storage.py::test_migration_v3_to_v4 -x` | Wave 0 |
| MIG-01 | `record_trace` with `parent_trace_id` round-trips correctly | unit | `pytest tests/test_storage.py::test_record_trace_with_parent -x` | Wave 0 |
| MA-02 | Shared `IterationBudget` exhaustion stops delegation tree | unit | `pytest tests/test_delegation.py::test_budget_exhaustion_stops_tree -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_delegation.py tests/test_storage.py -q --tb=short`
- **Per wave merge:** `python -m pytest tests/ -q`

### Wave 0 Gaps

- `tests/test_delegation.py` - all delegation tool tests (new file)
- `tests/test_storage.py` - add v3->v4 migration test and `record_trace` parent linkage test (extend existing file)

## Sources

### Primary (HIGH confidence)
- [VERIFIED: codebase inspection] `src/horus_os/agent.py`, `storage.py`, `tools/loop.py`, `tools/registry.py`, `types.py`, `_providers/_anthropic.py`, `_providers/_gemini.py` - full read of all relevant modules
- [VERIFIED: codebase inspection] `tests/test_storage.py`, `tests/test_agent.py` - test patterns confirmed
- [VERIFIED: SQLite 3.45.3] `ALTER TABLE ... ADD COLUMN` semantics

### Secondary (MEDIUM confidence)
- [CITED: Anthropic API] `system` parameter on `messages.create` for system prompts

### Tertiary (LOW confidence - see Assumptions Log)
- [ASSUMED] `ThreadPoolExecutor` sufficient for parallel sync delegation
- [ASSUMED] `IterationBudget` as shared mutable object is cleaner than passing remaining count as int

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new dependencies, all stdlib
- Architecture: HIGH - verified against existing codebase primitives
- Pitfalls: HIGH - derived from code reading, not guesswork
- Schema migration: HIGH - additive ALTER TABLE, safe on existing data

**Research date:** 2026-05-23
**Valid until:** 2026-06-23 (stable domain, no fast-moving dependencies)
