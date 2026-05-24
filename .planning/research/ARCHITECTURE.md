# Architecture Research — v0.4 Observability

**Domain:** Local-first observability for a single-process agent runtime
**Researched:** 2026-05-24
**Confidence:** HIGH (grounded in `ARCHITECTURE.md` v0.3 + direct source read of `agent.py`, `tools/loop.py`, `tools/registry.py`, `storage.py`, `server/api.py`, `_providers/_anthropic.py`)

This document is the v0.4 architecture brief. It assumes the v0.3 shape described in `/Users/santino/Projects/horus-os/ARCHITECTURE.md` and only proposes the additive deltas needed to satisfy the v0.4 requirements (METRIC, STORE, OTEL, DASH-4, PRICE, USAGE) without breaking v0.3 readers, byte-identical adapters, or schema-v3 databases.

## 0. The v0.3 surface, in one paragraph

`run_agent_loop` (in `horus_os.agent`) drives a multi-turn loop. Each turn it calls `Conversation.send` on a provider (`_providers/_anthropic.py`, `_providers/_gemini.py`), which returns an `AgentResult` carrying `text`, `tool_uses`, `provider`, `model`, and a `usage` dict with raw token counts. Tool calls inside that turn are dispatched by `execute_tool_uses` in `tools/loop.py`, which already times each call via `time.perf_counter()` and writes the duration onto `ToolResult.latency_ms`. At the end of the loop the FastAPI `/api/chat` handler calls `Database.record_trace(prompt, result, latency_ms=...)` and writes exactly one row to the `traces` table. Per-tool latency is forwarded to `on_tool_result` (used for the `tool_log` field in the HTTP response) but is **never persisted**. The `usage` column reflects only the **final** turn's token counts, not the loop sum. These two gaps are what v0.4 must close.

## 1. Standard Architecture (v0.4 deltas)

### 1.1 System Overview

```
+--------------------------------------------------------------------+
|                    DASHBOARD / CLI / OTEL                          |
+--------------------------------------------------------------------+
|  /observability tab    /agents tab        horus-os usage  OTLP    |
|       |                    |                    |         export  |
+-------|--------------------|--------------------|---------|--------+
        v                    v                    v         v
+--------------------------------------------------------------------+
|                    SERVER / READ + EXPORT LAYER                    |
+--------------------------------------------------------------------+
|  /api/observability/*  GET /api/agents (extended)  OtelAdapter    |
|         |                       |                       |          |
|         v                       v                       v          |
|   metrics_query.py         (reuses queries)        otel_export.py |
+---------|-------------------------|-----------------------|--------+
          |                         |                       |
          v                         v                       v
+--------------------------------------------------------------------+
|                    STORAGE  (SQLite WAL, schema v5)                |
+--------------------------------------------------------------------+
|  traces                    tool_invocations (NEW)    pricing_log  |
|  +turn_count               trace_id (FK)             (in-memory)  |
|  +total_input_tokens       parent_trace_id                         |
|  +total_output_tokens      tool_name                               |
|  +total_cost_usd           started_at, latency_ms                  |
|  +total_cache_*            status, error_message                   |
|                            input_hash, output_size                 |
|                                                                    |
|  llm_calls (NEW)           agent_profiles (unchanged)             |
|  trace_id (FK)             note_writes    (unchanged)             |
|  iteration_idx                                                     |
|  provider, model                                                   |
|  input_tokens, output_tokens, cache_*                              |
|  cost_usd                                                          |
|  latency_ms, started_at                                            |
+--------------------------------------------------------------------+
          ^                         ^
          |                         |
+---------|-------------------------|------------------+
|                  CAPTURE LAYER (in-process)          |
+------------------------------------------------------+
|  agent.py:run_agent_loop  ----+                      |
|   wraps every Conversation.send call,                |
|   pushes ObservationEvent.LLM_CALL                   |
|                                                       |
|  tools/loop.py:_execute_one ---+                     |
|   already times tool calls,                           |
|   pushes ObservationEvent.TOOL_CALL                  |
|                                                       |
|  All events flow through:  ObservationBus            |
|   (new module, sync in-process pub/sub)              |
|                                                       |
|  Built-in subscribers, attached at create_app time:  |
|    1. SQLitePersister  (always on)                   |
|    2. CostAnnotator    (always on, pricing lookup)   |
|    3. OtelExporter     (only if otel adapter active) |
+------------------------------------------------------+
          ^                         ^
          |                         |
   horus_os.agent          horus_os.tools.loop
   (LLM dispatch)          (tool dispatch)
```

### 1.2 Component Responsibilities

| Component | Module / function | Responsibility |
|-----------|-------------------|----------------|
| Capture point: LLM | `horus_os.agent.run_agent_loop` (modified) | Wrap each `conversation.send(...)`; time it; emit `ObservationEvent.LLM_CALL` per iteration |
| Capture point: tool | `horus_os.tools.loop._execute_one` (modified) | Reuses existing `time.perf_counter()`; emit `ObservationEvent.TOOL_CALL` per invocation |
| Bus | `horus_os.observability.bus.ObservationBus` (NEW) | Sync in-process pub/sub; `publish(event)` fans out to subscribers; per-subscriber exceptions swallowed like `_call_logger` already does |
| Pricing | `horus_os.observability.pricing.PricingTable` (NEW) | Loads `data/pricing.json` (package resource) once at startup; user-overridable via `cfg.pricing_path`; tag-tolerant lookup |
| Cost annotator | `horus_os.observability.cost.CostAnnotator` (NEW) | Subscribes to `LLM_CALL`; computes `cost_usd` from `usage` + pricing; mutates event in place before persister sees it |
| Persister | `horus_os.observability.persist.SQLitePersister` (NEW) | Subscribes to all events; writes one row to `llm_calls` per LLM call, one row to `tool_invocations` per tool call; updates `traces` totals on `RUN_END` |
| OTel exporter | `horus_os.adapters.otel_adapter.OtelAdapter` (NEW) | A v0.3-style `LifecycleAdapter`. On `start`: instantiate OTLP exporter, subscribe to bus. On `stop`: unsubscribe and flush. Opt-in via `[otel]` extra. |
| Query helper | `horus_os.observability.queries` (NEW) | Pure functions over the new tables: `agent_totals(window)`, `cost_by_agent(window)`, `latency_p50_p95(window)`, `tool_reliability(window)`. SQLite-side aggregation, not in-process. |
| Read API | `horus_os.server.api` (new routes) | `/api/observability/cost`, `/api/observability/latency`, `/api/observability/tools`, `/api/observability/llm-calls` — thin wrappers around `queries`. |
| Dashboard tab | `server/static/index.html` (new tab) | `/observability` view polls the four read routes every 5s; same vanilla-JS pattern as the Adapters tab. |
| CLI subcommand | `horus_os.cli.usage` (NEW) | `horus-os usage --since 7d --format json|csv|table`; uses the same `queries` module. |

## 2. Recommended Project Structure (additive)

```
src/horus_os/
+- agent.py                   # MODIFIED: wrap conversation.send timing + publish
+- storage.py                 # MODIFIED: v4 -> v5 migration, two new tables, helpers
+- tools/
|   +- loop.py                # MODIFIED: publish TOOL_CALL after each _execute_one
+- observability/             # NEW package
|   +- __init__.py
|   +- bus.py                 # ObservationEvent dataclasses + ObservationBus
|   +- pricing.py             # PricingTable + load_default_pricing()
|   +- pricing.json           # bundled package data (anthropic + gemini)
|   +- cost.py                # CostAnnotator subscriber
|   +- persist.py             # SQLitePersister subscriber
|   +- queries.py             # pure aggregation functions
+- adapters/
|   +- otel_adapter.py        # NEW: LifecycleAdapter wrapping OTLP exporter
+- cli/
|   +- usage.py               # NEW: horus-os usage subcommand
+- server/
    +- api.py                 # MODIFIED: 4 new GET routes + ObservationBus wiring
    +- static/
        +- index.html         # MODIFIED: new /observability tab
        +- observability.js   # NEW: tab-local JS module
```

### Structure Rationale

- **`observability/` as a sibling package, not under `tools/` or `storage.py`.** Three subsystems (cost, latency, reliability) cut across providers, tools, and adapters. Putting them under any one owner mixes concerns. A peer package mirrors how `memory/` and `adapters/` are already organized.
- **`pricing.json` bundled as package data inside `observability/`.** `importlib.resources.files("horus_os.observability") / "pricing.json"` is portable across editable installs, wheels, and zipapps. User override path stays in `Config`, not in the package.
- **`otel_adapter.py` lives in `adapters/`, not under `observability/`.** It is an adapter by every existing definition: it implements the `LifecycleAdapter` Protocol, declares an entry point in `pyproject.toml`, ships under an optional extra. Putting it alongside `discord_adapter.py` means dashboard auto-discovery and the Adapters tab status pill work for free.
- **CLI lives in `cli/usage.py`** to match `cli/init.py`, `cli/run.py`, etc. Argparse subcommand register, no new pattern.

## 3. Architectural Patterns

### Pattern 1: In-process synchronous observation bus

**What:** A `ObservationBus` object held on `app.state.observation_bus` (and accessible via a module-level fallback for CLI / direct-API callers). `publish(event)` walks the subscriber list and calls each handler synchronously, swallowing handler exceptions exactly like `_call_logger` in `tools/loop.py` already does.

**When to use:** Whenever a v0.4 capture point fires (LLM call complete, tool call complete, agent run end). Replaces direct `db.record_trace()` calls in the runner so OTel + SQLite + CLI all see the same events.

**Trade-offs:**
- **Pro:** Multiple consumers (SQLite, OTel, future webhook) decouple cleanly. No subscriber can starve another because dispatch is sync.
- **Pro:** Sync matters for SQLite-first correctness: the row is committed before `record_trace` returns, so a crash mid-loop never loses the partial cost data.
- **Pro:** No event loop dependency — the bus works identically in `run_agent_loop` (sync) and CLI scripts.
- **Con:** A slow subscriber blocks the agent's next provider call. OTel exporter must do `BatchSpanProcessor`-style background queuing on its own side, not on the bus. The bus contract is "deliver fast or own your async."

**Example:**

```python
# horus_os/observability/bus.py
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

EventKind = Literal["RUN_START", "LLM_CALL", "TOOL_CALL", "RUN_END"]

@dataclass
class ObservationEvent:
    kind: EventKind
    trace_id: str
    parent_trace_id: str | None = None
    iteration_idx: int = 0
    provider: str = ""
    model: str = ""
    tool_name: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cost_usd: float | None = None     # filled by CostAnnotator
    latency_ms: int = 0
    status: str = "success"
    error_message: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

class ObservationBus:
    def __init__(self) -> None:
        self._subscribers: list[Callable[[ObservationEvent], None]] = []
    def subscribe(self, handler):
        self._subscribers.append(handler)
        return lambda: self._subscribers.remove(handler)
    def publish(self, event: ObservationEvent) -> None:
        for h in self._subscribers:
            try:
                h(event)
            except BaseException:
                pass  # match _call_logger semantics
```

### Pattern 2: Capture at the narrowest stable boundary

**What:** Instrument exactly two functions, both at the boundary where the operation is unambiguously "one observable unit":

1. `horus_os.agent.run_agent_loop` — wraps each `conversation.send(...)` call. This is the right scope because (a) one `send()` is exactly one LLM HTTP request, (b) the provider's `usage` dict is parsed at this point and freshly available, (c) the iteration index is in scope, (d) it works identically for Anthropic and Gemini without provider-layer changes.
2. `horus_os.tools.loop._execute_one` — already times each tool. v0.4 just adds a `bus.publish(...)` after the existing `time.perf_counter()` block. No new timing code; no new threading concern.

**When to use:** Always. Don't instrument inside provider modules (`_providers/_anthropic.py`, `_providers/_gemini.py`); that doubles the change surface for every new provider. Don't instrument inside `Database.record_trace`; that's persistence, not capture.

**Trade-offs:**
- **Pro:** Two modified files vs. four-plus if we instrument per provider. Anthropic streaming, Gemini streaming, sync, async — all funnel through `run_agent_loop` and `_execute_one`.
- **Pro:** Tool timing already works in v0.3; we are wiring it into a new bus, not adding a new instrument.
- **Con:** `/api/chat/stream` does **not** route through `run_agent_loop` (it uses `run_agent_stream` directly and never executes tools). v0.4 must also wrap the SSE branch in `server/api.py` to publish a single `LLM_CALL` event. Acceptable: SSE is a known second capture site, documented and bounded.

### Pattern 3: Additive schema migration, never destructive

**What:** Schema v4 (current) keeps every column. Schema v5 (v0.4):
- **`traces` gets four new columns** via `ALTER TABLE ADD COLUMN IF NOT EXISTS`, all nullable so v0.3 row reads are unaffected: `turn_count INTEGER`, `total_input_tokens INTEGER`, `total_output_tokens INTEGER`, `total_cost_usd REAL`. (Cache tokens stay on `llm_calls` only — they're per-call detail.)
- **Two new tables:** `llm_calls` (one row per `Conversation.send`) and `tool_invocations` (one row per `_execute_one`). Both carry `trace_id` as a soft foreign key (no `REFERENCES` clause, matching the existing `note_writes.trace_id` pattern that leaves the join responsibility to readers).
- **Existing `traces.usage` JSON blob is left in place and still written.** v0.3 readers continue to parse it. v0.4 readers prefer the typed columns. No row of either schema is rewritten.

**When to use:** Every storage change in this milestone. Mirrors the v3→v4 pattern in `storage.py:125-152` exactly: `ALTER TABLE ... ADD COLUMN`, wrapped in a `try/except sqlite3.OperationalError` for idempotency, with index creation pulled out of `SCHEMA_SQL` so it runs after the ALTER.

**Trade-offs:**
- **Pro:** A user who rolls back to v0.3 (`pip install horus-os==0.3.0`) keeps reading their database. v5 schema is a strict superset.
- **Pro:** No data migration script. Backfill is implicit: new runs populate the new columns; old runs leave them null; dashboard queries are written to handle null with `COALESCE`.
- **Con:** `total_input_tokens` won't exist for any v0.3 trace, so cost totals before the upgrade show as zero. Acceptable and called out in the migration doc; nobody reasonably expects retroactive cost data.

### Pattern 4: Aggregations live in SQLite, not in Python

**What:** Use SQLite window functions and `GROUP BY` for `p50`/`p95`/sums/counts, not in-process accumulators. Example:

```sql
-- p50 / p95 over last 7 days, per agent
WITH ranked AS (
  SELECT
    agent_profile_name,
    latency_ms,
    NTILE(100) OVER (PARTITION BY agent_profile_name ORDER BY latency_ms) AS pct
  FROM traces
  WHERE created_at >= ? AND latency_ms IS NOT NULL
)
SELECT
  agent_profile_name,
  MAX(CASE WHEN pct <= 50 THEN latency_ms END) AS p50,
  MAX(CASE WHEN pct <= 95 THEN latency_ms END) AS p95,
  COUNT(*) AS sample_count
FROM ranked
GROUP BY agent_profile_name;
```

**When to use:** All dashboard and CLI aggregations. Local-first means the user's data lives in one file; SQLite is already loaded; reaching for in-process accumulation reintroduces "metrics vanish on restart" — the exact failure mode the local-first constraint forbids.

**Trade-offs:**
- **Pro:** Survives restart. Zero memory cost for unbounded run history.
- **Pro:** SQLite 3.25+ supports window functions; both Python 3.11 and 3.12 ship modern-enough SQLite on macOS, Ubuntu, Windows. (Verified: stdlib `sqlite3.sqlite_version` on Python 3.11+ is ≥ 3.34 on all three OSes.)
- **Con:** Queries over millions of rows get slow. Mitigation: indexes on `(created_at, agent_profile_name)` and `(trace_id)`. At 100k-row scale, the brute-force `NTILE` is still sub-100ms locally — well under the dashboard's 5-second poll cadence.
- **Alternative considered and rejected:** A precomputed `rollups_hourly` table. Adds a background job, adds a migration concern, adds drift between rollups and source rows. Defer to v0.5 if dashboard queries actually get slow; don't optimize before the data exists.

### Pattern 5: OTel exporter as adapter, not as a fork in the bus

**What:** `OtelAdapter` implements the `Adapter` + `LifecycleAdapter` Protocols exactly like `DiscordAdapter` does. On `start(context)`: lazy-import `opentelemetry-sdk`, configure OTLP exporter from env (`OTEL_EXPORTER_OTLP_ENDPOINT`, etc.), call `context.observation_bus.subscribe(self._on_event)`. On `stop()`: unsubscribe and call `tracer_provider.shutdown()` to flush pending batches.

**When to use:** Always, for OTel specifically and for any future external sink. This makes OTel disable/enable-able from the dashboard Adapters tab the moment it ships — no new toggle UI required.

**Trade-offs:**
- **Pro:** Reuses every piece of v0.3 infrastructure: discovery via entry points, lifespan-managed start/stop, `AdapterRegistry` status, dashboard pill. Zero new "is OTel running?" plumbing.
- **Pro:** Lazy import means installing `horus-os` without `[otel]` extra never hits `opentelemetry` import errors.
- **Pro:** When OTel is disabled at runtime via `POST /api/adapters/otel/disable`, the SQLite persister keeps running because it's not an adapter — it's wired in `create_app` and runs for the process lifetime.
- **Con:** `AdapterContext` needs a new optional field, `observation_bus: ObservationBus | None`, in the same additive pattern as Phase 26's `tool_registry`. v0.3 third-party adapters keep working because the field defaults to None.

### Pattern 6: Pricing as data, not code

**What:** `pricing.json` ships as package data:

```json
{
  "version": 1,
  "updated_at": "2026-05-24",
  "models": {
    "claude-sonnet-4-6": {
      "provider": "anthropic",
      "input_per_million": 3.00,
      "output_per_million": 15.00,
      "cache_write_per_million": 3.75,
      "cache_read_per_million": 0.30
    },
    "gemini-2.5-pro": { ... }
  },
  "fallback": { "input_per_million": 0, "output_per_million": 0, "cache_write_per_million": 0, "cache_read_per_million": 0 }
}
```

Loaded once at `create_app` startup via `PricingTable.load_default()`. User override path is `cfg.pricing_path` (set in config file, env var `HORUS_OS_PRICING_PATH` overrides). Unknown models fall back to the `fallback` block (cost = 0 with a `pricing_missing: true` flag on the event so the dashboard can warn the user).

**When to use:** All cost computation. Never hardcode prices in `cost.py`.

**Trade-offs:**
- **Pro:** Pricing changes ship as a one-line PR (data, no test surface).
- **Pro:** Users with private model deployments override one path in config; no monkey-patching.
- **Con:** Stale pricing between releases. Mitigation: each release refreshes the file; the dashboard surfaces `updated_at` next to cost totals so the user knows the asof date.
- **Hot-reload rejected:** Adds file-watcher dependency and threading complexity for a number that changes monthly. Reload happens on process restart, which is normal for a desktop app.

## 4. Data Flow

### 4.1 The end-to-end path: agent run → cost/latency captured → SQLite → dashboard → OTel

```
HTTP POST /api/chat  (or CLI horus-os run)
        |
        v
  create_app wires:
    bus = ObservationBus()
    bus.subscribe(CostAnnotator(pricing).on_event)
    bus.subscribe(SQLitePersister(db).on_event)
    if otel_adapter active: bus.subscribe(otel_adapter.on_event)
        |
        v
  run_agent_loop(prompt, registry, ...)
    trace_id = uuid4()
    bus.publish(RUN_START, trace_id=trace_id)
        |
        |  iteration 0
        v
    t0 = perf_counter()
    result = conversation.send(prompt, tools)
    dt = perf_counter() - t0
    bus.publish(LLM_CALL,
        trace_id=trace_id, iteration_idx=0,
        provider="anthropic", model="claude-sonnet-4-6",
        input_tokens=result.usage["input_tokens"], ...
        latency_ms=int(dt*1000))
        |
        v
    [SUBSCRIBER 1] CostAnnotator.on_event(ev):
        ev.cost_usd = pricing.compute(ev)   # mutates the event
        |
        v
    [SUBSCRIBER 2] SQLitePersister.on_event(ev):
        INSERT INTO llm_calls (...)         # one row, one commit
        |
        v
    [SUBSCRIBER 3] OtelExporter.on_event(ev):
        span = tracer.start_span("llm_call")
        span.set_attribute("llm.model", ev.model)
        span.set_attribute("llm.cost.usd", ev.cost_usd)
        span.end()                          # BatchSpanProcessor queues, returns fast
        |
        v
    execute_tool_uses(registry, result, on_log=...)
        |
        |  per tool_use
        v
        _execute_one runs tool, captures latency_ms
        bus.publish(TOOL_CALL, trace_id=trace_id, tool_name=u.name,
                   latency_ms=outcome.latency_ms,
                   status="error" if outcome.error else "success",
                   error_message=outcome.error)
        |
        |  (same 3 subscribers fire)
        v
    [next iteration or loop exit]
        |
        v
    bus.publish(RUN_END, trace_id=trace_id, latency_ms=total_ms)
    [SQLitePersister]: UPDATE traces
                         SET turn_count = (SELECT COUNT(*) FROM llm_calls WHERE trace_id=?),
                             total_input_tokens = (SELECT SUM(input_tokens) FROM llm_calls WHERE trace_id=?),
                             total_output_tokens = (SELECT SUM(output_tokens) FROM llm_calls WHERE trace_id=?),
                             total_cost_usd = (SELECT SUM(cost_usd) FROM llm_calls WHERE trace_id=?)
                         WHERE trace_id = ?
        |
        v
    db.record_trace(prompt, result, latency_ms=total_ms)   # existing v0.3 call, unchanged
        |
        v
    return AgentResult to HTTP handler / CLI
```

### 4.2 Dashboard read flow

```
Dashboard /observability tab
   poll every 5s
        |
        v
  GET /api/observability/cost?since=7d
        |
        v
  server/api.py route handler
        |
        v
  queries.cost_by_agent(db, since="7d")
        |
        v
  SQL: SELECT agent_profile_name, SUM(total_cost_usd) AS cost,
              SUM(total_input_tokens) AS in_tokens, ...
       FROM traces WHERE created_at >= ? GROUP BY agent_profile_name
        |
        v
  JSON: [{agent: "ralph", cost_usd: 0.42, runs: 17, ...}, ...]
        |
        v
  observability.js renders bar chart + numbers
```

### 4.3 Key data flows summarized

1. **Capture:** `run_agent_loop` and `_execute_one` publish `LLM_CALL` and `TOOL_CALL` events into `ObservationBus` immediately after each operation.
2. **Annotate:** `CostAnnotator` runs first; it mutates each `LLM_CALL` event with `cost_usd` derived from `PricingTable` lookup.
3. **Persist:** `SQLitePersister` inserts one row per event into `llm_calls` or `tool_invocations`. On `RUN_END`, it updates the `traces` row with rolled-up totals.
4. **Export (optional):** If `OtelAdapter` is running, the same events are converted to OTLP spans and queued for background export.
5. **Read:** Dashboard tab and `horus-os usage` CLI both call `queries.py` functions which return SQLite-aggregated results.

### 4.4 Streaming path (the second capture site)

`/api/chat/stream` does not call `run_agent_loop`; it iterates `run_agent_stream` directly and never executes tools. v0.4 instruments it in `server/api.py:_event_stream`:

```python
start = time.perf_counter()
# ... existing token streaming ...
latency_ms = int((time.perf_counter() - start) * 1000)
# v0.4: publish one LLM_CALL event before db.record_trace
bus.publish(ObservationEvent(
    kind="LLM_CALL", trace_id=trace_id, iteration_idx=0,
    provider=provider, model=model,
    input_tokens=0,  # streaming doesn't surface usage in SSE today; documented gap
    output_tokens=0,
    latency_ms=latency_ms,
    status="success",
))
bus.publish(ObservationEvent(kind="RUN_END", trace_id=trace_id, latency_ms=latency_ms))
```

The streaming `usage` gap is a known v0.3 limitation (the SSE response shape doesn't carry token counts back to the client). v0.4 accepts it: cost tracking is best-effort on the streaming path, and the dashboard surfaces a `streaming_run: true` flag so users understand why these runs show $0.00.

## 5. Schema Migration (v4 → v5, additive)

```sql
-- traces: 4 new nullable columns (no breaking reads)
ALTER TABLE traces ADD COLUMN turn_count INTEGER;
ALTER TABLE traces ADD COLUMN total_input_tokens INTEGER;
ALTER TABLE traces ADD COLUMN total_output_tokens INTEGER;
ALTER TABLE traces ADD COLUMN total_cost_usd REAL;

-- llm_calls: one row per Conversation.send
CREATE TABLE IF NOT EXISTS llm_calls (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id                     TEXT NOT NULL UNIQUE,
    trace_id                    TEXT NOT NULL,
    iteration_idx               INTEGER NOT NULL,
    created_at                  TEXT NOT NULL,
    provider                    TEXT NOT NULL,
    model                       TEXT NOT NULL,
    input_tokens                INTEGER NOT NULL DEFAULT 0,
    output_tokens               INTEGER NOT NULL DEFAULT 0,
    cache_creation_input_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_input_tokens     INTEGER NOT NULL DEFAULT 0,
    cost_usd                    REAL,
    pricing_missing             INTEGER NOT NULL DEFAULT 0,
    latency_ms                  INTEGER NOT NULL,
    status                      TEXT NOT NULL DEFAULT 'success',
    error_message               TEXT
);
CREATE INDEX IF NOT EXISTS idx_llm_calls_trace_id   ON llm_calls(trace_id);
CREATE INDEX IF NOT EXISTS idx_llm_calls_created_at ON llm_calls(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_calls_model      ON llm_calls(provider, model);

-- tool_invocations: one row per _execute_one
CREATE TABLE IF NOT EXISTS tool_invocations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    invocation_id   TEXT NOT NULL UNIQUE,
    trace_id        TEXT NOT NULL,
    parent_trace_id TEXT,
    created_at      TEXT NOT NULL,
    tool_name       TEXT NOT NULL,
    latency_ms      INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'success',
    error_message   TEXT,
    output_size     INTEGER
);
CREATE INDEX IF NOT EXISTS idx_tool_invocations_trace_id   ON tool_invocations(trace_id);
CREATE INDEX IF NOT EXISTS idx_tool_invocations_tool_name  ON tool_invocations(tool_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_invocations_created_at ON tool_invocations(created_at DESC);
```

Migration runs in the existing `Database.init()` block, wrapped in `try/except sqlite3.OperationalError` (the exact pattern at `storage.py:137-146`). Indexes are created post-ALTER so they apply on both fresh and upgraded databases.

`SCHEMA_VERSION` bumps from 4 to 5. The `if stored_version is not None and stored_version < 4` block grows a peer for `< 5`.

**No row of an existing table is rewritten.** Pre-v5 `traces` rows have null `turn_count`/`total_*` columns and are simply absent from cost rollups.

## 6. Scaling Considerations

| Scale | Architecture adjustments |
|-------|--------------------------|
| 0–10k runs (typical first-year user) | No changes. The full v0.4 design as described. Indexes on `created_at` and `trace_id` give sub-100ms queries. SQLite WAL handles concurrent reads while the agent writes. |
| 10k–1M runs (heavy single user, multi-year) | Add the `INTEGER` window-function aggregation cache only if a dashboard query exceeds 500ms in observed practice. SQLite remains adequate to ~10M rows for the query patterns described. |
| 1M+ runs | Out of scope. Local-first single-user desktop tool. If a user reaches this scale they are running a different system. |

### Scaling priorities (what breaks first)

1. **Bus subscriber stalls block the agent loop.** Sync dispatch is the contract. The OTel exporter must offload to its own batch processor. SQLitePersister must keep individual inserts fast (< 1ms typical, well under provider-call latency).
2. **`llm_calls` row count grows fastest** (one per provider call vs. one trace per multi-turn run). After ~500k rows, watch for the `created_at` index range scans. Mitigation: a `VACUUM` documented in `docs/MAINTENANCE.md`; no runtime work.
3. **Pricing drift** breaks `total_cost_usd` accuracy across release boundaries. Mitigation: `updated_at` field surfaced in dashboard footer.

## 7. Anti-Patterns

### Anti-Pattern 1: "Capture inside the provider modules"

**What people do:** Add timing + token capture inside `_providers/_anthropic.py` and `_providers/_gemini.py` so the data is "closest to the source."
**Why wrong:** Doubles the change surface for every new provider, leaks observability concerns into a layer whose only job is SDK shape translation. Misses the iteration index (the provider has no concept of where it sits in a tool loop).
**Do instead:** Capture in `run_agent_loop`, where `iteration_idx`, `trace_id`, and `agent_profile_name` are all in scope.

### Anti-Pattern 2: "Compute p50/p95 in Python after fetching all rows"

**What people do:** Pull every trace from SQLite into a list, sort by latency, index at 0.5 * len.
**Why wrong:** OOM at scale, slow at any scale, ignores SQLite's native window functions. Mixes presentation logic into the read path.
**Do instead:** Use `NTILE(100) OVER (...)` in SQL. Returns one summarized row per agent in a single round trip.

### Anti-Pattern 3: "In-memory ring buffer of recent runs as the dashboard source"

**What people do:** Hold the last 1000 events in a Python deque so the dashboard "feels fast."
**Why wrong:** Restart = data gone. Two processes (CLI + server) = inconsistent views. Violates the local-first constraint that says SQLite is the source of truth.
**Do instead:** Persist first, query SQLite for the dashboard. If query latency is an issue, fix it with indexes or rollup tables, not with an in-process cache.

### Anti-Pattern 4: "OTel exporter as a forked code path inside `run_agent_loop`"

**What people do:** `if otel_enabled: tracer.start_span(...)` sprinkled through the loop.
**Why wrong:** Optional dependency becomes a hard import; runtime grows an `if` per capture point; the exporter can't be toggled at runtime without restarting the process.
**Do instead:** Exporter is a bus subscriber attached by the `OtelAdapter` at adapter `start`. Runner doesn't know it exists. Toggle works through the existing `/api/adapters/{name}/{enable,disable}` routes.

### Anti-Pattern 5: "Pricing as a constant dict in `cost.py`"

**What people do:** `MODEL_PRICES = {"claude-sonnet-4-6": (3.0, 15.0), ...}` at module top.
**Why wrong:** Releases get blocked on a pricing edit. Users can't override for private deployments. Test fixtures freeze the prices.
**Do instead:** `PricingTable` loaded from `pricing.json`, with `pricing_path` config override.

### Anti-Pattern 6: "Rewrite `traces.usage` JSON when migrating to v5"

**What people do:** A migration script that walks every existing trace row, parses `usage`, and backfills `total_input_tokens`.
**Why wrong:** Breaks the additive-only contract. Risks corruption on interrupted migrations. The numbers it backfills are misleading because pre-v0.4 only the final iteration's tokens were captured.
**Do instead:** Leave pre-v5 rows alone. Document that cost data is forward-looking from the v0.4 upgrade. The dashboard renders "no cost data for runs before YYYY-MM-DD" rather than fake zeros.

## 8. Integration Points

### 8.1 External services

| Service | Integration pattern | Notes |
|---------|---------------------|-------|
| OTLP collector (any user-run backend: Jaeger, Tempo, Honeycomb local, Grafana Tempo, etc.) | `OtelAdapter` (LifecycleAdapter, opt-in via `[otel]` extra). Env vars: standard OTel — `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_SERVICE_NAME` (default `horus-os`). | No paid SaaS dependency; user brings their own collector. If `OTEL_EXPORTER_OTLP_ENDPOINT` is unset at adapter `start`, the adapter logs a clear error to `AdapterRegistry` and stays in `error` state. Dashboard Adapters tab surfaces it. |
| Anthropic API | Unchanged from v0.3 (`_providers/_anthropic.py`). v0.4 reads `usage` from the existing `_parse_anthropic_response`. | Already captures `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`. No SDK changes needed. |
| Google Gemini API | Unchanged. `_providers/_gemini.py` already returns a `usage` dict. v0.4 confirms it carries `prompt_token_count` / `candidates_token_count`; pricing maps these to the standardized field names in `ObservationEvent`. | One-line adjustment in `_providers/_gemini.py` to normalize the dict keys to match Anthropic's, so `CostAnnotator` sees a single shape. |

### 8.2 Internal boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `agent.run_agent_loop` ↔ `ObservationBus` | Direct call (`bus.publish(event)`) | Bus reference passed via a module-level setter or kwarg; default to a no-op bus if unset so unit tests don't need wiring. |
| `tools.loop._execute_one` ↔ `ObservationBus` | Same direct call pattern | Bus reference passed via the registry or kwarg; defaults to no-op. |
| `ObservationBus` ↔ `CostAnnotator` / `SQLitePersister` | `bus.subscribe(handler)` at `create_app` time | Subscribers attached once per app instance. Order matters: CostAnnotator first (mutates event), Persister second (reads the mutated event), OtelExporter last (read-only). |
| `OtelAdapter` ↔ `ObservationBus` | `context.observation_bus.subscribe(...)` in adapter `start` | New optional field on `AdapterContext`: `observation_bus: ObservationBus | None`. Additive, defaults to None. Third-party v0.3 adapters keep working byte-identical. |
| `queries.py` ↔ dashboard | Pure functions returning JSON-serializable dicts; HTTP route is a one-line wrapper | Keeps the query module testable without spinning up FastAPI. The CLI `horus-os usage` calls the same functions, guaranteeing dashboard and CLI never disagree. |
| `Database.record_trace` ↔ `SQLitePersister` | `SQLitePersister` calls `db.update_trace_totals(trace_id, ...)` on `RUN_END`. `record_trace` itself stays unchanged. | New helper method `Database.update_trace_totals` is the only v0.4 addition to `storage.py`'s public surface. |

## 9. Build Order (phases inside the v0.4 milestone)

A correct build order respects: capture before storage before query before exporter (you cannot query what you have not stored, you cannot export what was never captured). This sequence also ships a usable slice after each step.

### Phase v0.4.1 — Schema + persistence skeleton

**Files:** `storage.py` migration v4→v5, `observability/bus.py`, `observability/persist.py`.
**What ships:** `Database.init()` now creates `llm_calls` and `tool_invocations` tables. `ObservationBus` exists. `SQLitePersister` subscribes and writes rows. Bus is **not yet wired** into the runner, so no events flow. Pure infrastructure phase.
**Validation:** Unit tests insert events directly via `bus.publish(...)` and verify rows land in the right tables. Schema migration test against a v4 fixture database confirms additive idempotency.

### Phase v0.4.2 — Capture at the runner

**Files:** `agent.py:run_agent_loop` modified, `tools/loop.py:_execute_one` modified, `server/api.py` (SSE path).
**What ships:** Real runs produce real rows in `llm_calls` and `tool_invocations`. `cost_usd` is still null at this point.
**Validation:** Run a single chat turn end-to-end; verify N llm_calls + M tool_invocations rows match observed iterations. Existing v0.3 trace row is also written (parallel-path proves additive).

### Phase v0.4.3 — Pricing + cost annotation

**Files:** `observability/pricing.py`, `observability/pricing.json`, `observability/cost.py`, `config.py` (add `pricing_path`).
**What ships:** `CostAnnotator` is wired into the bus before the persister. Cost rows populate. The `traces.total_cost_usd` rollup is updated on `RUN_END`. `pricing.json` ships with current Anthropic + Gemini prices.
**Validation:** Test fixture sends a known token count, asserts cost matches `(tokens / 1M) * price`. Test that an unknown model produces `pricing_missing=1, cost_usd=NULL`.

### Phase v0.4.4 — Query module + read APIs

**Files:** `observability/queries.py`, `server/api.py` (4 new routes).
**What ships:** `/api/observability/cost`, `/api/observability/latency`, `/api/observability/tools`, `/api/observability/llm-calls` all return real aggregated data. The `/api/agents` route is extended to include `total_runs`, `total_cost_usd`, `latency_p50`, `latency_p95` per agent.
**Validation:** Curl each route after a seeded set of runs; verify p50/p95 against hand-computed values. Confirm `NTILE` window functions return the expected percentile boundaries on Python 3.11 + 3.12 stdlib SQLite across macOS/Ubuntu/Windows.

### Phase v0.4.5 — Dashboard /observability tab

**Files:** `server/static/index.html` (tab nav), `server/static/observability.js` (new module).
**What ships:** New /observability tab with three panels (cost-by-agent bar chart, latency p50/p95 table, tool reliability list). Existing /agents tab gets the new columns. 5-second poll cadence, same vanilla-JS pattern as Adapters tab.
**Validation:** Browser smoke test on each OS; verify last-7d and last-30d filter selectors work; verify charts render after each poll.

### Phase v0.4.6 — `horus-os usage` CLI

**Files:** `cli/usage.py`, register subparser in `cli/__init__.py` (or wherever `init`/`run` are registered).
**What ships:** `horus-os usage --since 7d --format table` prints a human table. `--format json` / `--format csv` emit machine-readable output via stdout.
**Validation:** Run on a seeded database; pipe to `jq` and `column -t -s,` to confirm valid output. Matches what `/api/observability/cost` returns.

### Phase v0.4.7 — OTel adapter

**Files:** `adapters/otel_adapter.py`, `adapters/base.py` (add `observation_bus: ObservationBus | None` to `AdapterContext`), `pyproject.toml` (`[otel]` extra), entry-point registration.
**What ships:** With `pip install horus-os[otel]` and `OTEL_EXPORTER_OTLP_ENDPOINT` set, the adapter appears in `/api/adapters` and starts forwarding spans on app startup. Dashboard Adapters tab shows it. Disable/enable routes work.
**Validation:** Point at a local Jaeger; verify spans appear with the expected attributes. Confirm that disabling the adapter via the dashboard immediately stops new span emission (subscriber unsubscribes in `stop()`).

### Phase v0.4.8 — Three-OS gate, release, migration doc

**Files:** `docs/MIGRATION-v0.3-to-v0.4.md`, `CHANGELOG.md`, version bump.
**What ships:** v0.4.0 tag.
**Validation:** Existing CI matrix (macOS + Ubuntu + Windows × Python 3.11 + 3.12) green on the full test suite plus the new observability tests.

### Why this order

- **v0.4.1 before v0.4.2:** Capture would fail if there were no tables to insert into.
- **v0.4.2 before v0.4.3:** Cost annotation needs events to annotate. Pricing without events is dead code.
- **v0.4.3 before v0.4.4:** Query rollups read `total_cost_usd`. Querying nulls is allowed but uninteresting.
- **v0.4.4 before v0.4.5:** Dashboard fetches from these routes. Routes must exist first.
- **v0.4.4 before v0.4.6:** CLI uses the same query module. Module must exist; routes optional but parallel.
- **v0.4.7 last:** OTel is opt-in. Shipping it earlier would mean wiring `AdapterContext.observation_bus` before the bus is used internally, which is order-of-changes confusion. By v0.4.7 the bus has six commits of stability.

## 10. Decisions explicitly made (and rejected alternatives)

| Decision | Picked | Rejected | Reason |
|----------|--------|----------|--------|
| Capture site for LLM cost/latency | `run_agent_loop` wrapping each `conversation.send` | Inside each provider module | One change point covers both providers + future ones; iteration index in scope |
| Capture site for tool latency | `tools/loop.py:_execute_one` (already times; just publish) | New decorator on every tool handler | Zero new timing code; works for delegated tools automatically |
| Storage shape | Extend `traces` + two new tables (`llm_calls`, `tool_invocations`) | JSON blob columns on `traces` only | Joins, indexed scans, and SQL aggregations are easier on real columns; rollup totals on `traces` keep `/api/traces` summary fast |
| Capture-to-storage transport | In-process synchronous `ObservationBus` | Direct `db.record_*` calls in the runner | Bus admits multiple consumers (SQLite, OTel) without forking the runner |
| Sync vs async bus | Sync | Async (`asyncio.Queue`) | Runner has sync and async entry points; sync works in both; SQLite write is fast enough; matches existing `_call_logger` swallow-exceptions semantics |
| OTel consumption | Adapter (LifecycleAdapter, opt-in extra) | Separate plugin system, or hard dependency | Reuses v0.3 adapter discovery, lifespan, status registry, dashboard tab; opt-in is automatic |
| Pricing source | Bundled `pricing.json`, user-overridable | Hardcoded dict in `cost.py`, or fetched at runtime | Data not code; release-friendly; user override path required for private deployments; runtime fetch violates "no silent network calls" principle |
| Percentile computation | SQLite `NTILE` window functions | In-process tdigest / numpy | Local-first; survives restart; SQLite ≥ 3.25 ships everywhere we support; data already there |
| Dashboard data source | REST over SQLite aggregations on each poll | Precomputed rollups table | Premature; query latency adequate at expected scale; no drift risk; can add rollups later additively |
| Migration shape | Pure additive (`ALTER ADD COLUMN`, new tables) | Rewrite existing rows to backfill | Rollback safety; pre-v0.4 cost data would be misleading anyway |

## 11. The five quality-gate questions, answered

1. **Capture points named to module/function granularity?** Yes: `horus_os.agent.run_agent_loop` (wraps `conversation.send`), `horus_os.tools.loop._execute_one` (already times; adds publish), `horus_os.server.api._event_stream` (SSE path).
2. **Migration additive?** Yes: 4 `ALTER ADD COLUMN` on `traces` (all nullable), 2 `CREATE TABLE IF NOT EXISTS` for new tables. No row rewrites. Existing v0.3 columns and rows untouched.
3. **Event-bus vs direct-write, justified?** Event bus picked. Justification: OTel exporter must consume the same events as the SQLite persister; forking that in the runner means an `if` per capture point and a hard-import problem for the optional extra. Bus dispatch is sync (not async) so the runner's existing semantics — including swallow-on-subscriber-exception — are preserved verbatim.
4. **OTel consumption pattern explicit?** Yes: `OtelAdapter implements LifecycleAdapter`. `start(context)` subscribes to `context.observation_bus`; `stop()` unsubscribes and shuts the tracer down. Toggle works through existing `/api/adapters/{name}/enable|disable` routes. Lazy-imports `opentelemetry-sdk` so the package imports cleanly without the `[otel]` extra.
5. **p50/p95 strategy picked with reason?** SQLite `NTILE(100) OVER (...)`. Reason: local-first means persisted-first; in-process accumulators vanish on restart; the data is already in SQLite; window functions ship in every stdlib SQLite on the supported matrix; query latency is sub-100ms at expected scale.

## Sources

- `/Users/santino/Projects/horus-os/ARCHITECTURE.md` — v0.3 reference (direct read)
- `/Users/santino/Projects/horus-os/.planning/PROJECT.md` — v0.4 requirements list (direct read)
- `/Users/santino/Projects/horus-os/src/horus_os/agent.py` — `run_agent_loop` shape (direct read)
- `/Users/santino/Projects/horus-os/src/horus_os/tools/loop.py` — existing tool-call timing (direct read)
- `/Users/santino/Projects/horus-os/src/horus_os/tools/registry.py` — `ToolRegistry` invoke path (direct read)
- `/Users/santino/Projects/horus-os/src/horus_os/storage.py` — schema v4 + migration pattern (direct read)
- `/Users/santino/Projects/horus-os/src/horus_os/server/api.py` — FastAPI app factory + lifespan + SSE branch (direct read)
- `/Users/santino/Projects/horus-os/src/horus_os/_providers/_anthropic.py` — usage extraction (direct read)
- `/Users/santino/Projects/horus-os/src/horus_os/types.py` — `AgentResult.usage`, `ToolResult.latency_ms` (direct read)
- OpenTelemetry Python SDK lifecycle (LOW confidence, training data) — exporter shutdown semantics confirmed via SDK docs convention; verify in v0.4.7 implementation

---
*Architecture research for: horus-os v0.4 Observability*
*Researched: 2026-05-24*
