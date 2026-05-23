---
phase: 03-persistence-layer
plan: "00"
subsystem: storage
tags: [sqlite, wal, traces, persistence, schema-v1]

# Dependency graph
requires:
  - phase: "02-agent-runtime-core"
    provides: "AgentResult dataclass, ToolUse dataclass, run_agent entry points that produce the data being persisted"
provides:
  - "`horus_os.storage.Database` class with init, record_trace, list_traces, get_trace"
  - "`horus_os.storage.TraceRecord` dataclass mirroring the persisted row with decoded JSON fields"
  - "`SCHEMA_VERSION = 1` and `SCHEMA_SQL` constants for migration tracking"
  - "WAL + sane pragma defaults enabled per connection"
affects:
  - "Phase 04 (tool registry) will record handler invocations alongside tool_use intents"
  - "Phase 07 (CLI) will surface `horus-os traces` listing the persisted rows"
  - "Phase 08 (web chat + dashboard) will read from the same SQLite file and stream new traces"
  - "Phase 09 (setup wizard) will decide the canonical on-disk path for the SQLite file"

# Tech tracking
tech-stack:
  added: []  # sqlite3 is in the standard library
  patterns:
    - "Per-operation connection lifecycle: open, run, close. No long-lived connection. Safe across threads without extra coordination."
    - "Idempotent schema via `CREATE TABLE IF NOT EXISTS` and a guarded `INSERT INTO schema_version` so re-init is a no-op."
    - "JSON serialization of structured fields (tool_uses, usage) with graceful degrade on corrupted data."
    - "UUID4 hex strings as external trace identifiers, independent of the autoincrement primary key."

key-files:
  created:
    - "src/horus_os/storage.py, 201 lines, Database + TraceRecord + schema constants"
    - "tests/test_storage.py, 165 lines, 12 tmp_path-based tests"
  modified:
    - "src/horus_os/__init__.py, re-exports Database and TraceRecord"

key-decisions:
  - "One table for v0.1. traces is both the unit-of-work record and the trace. When multi-turn conversations land in v0.2 a `tasks` table can join via task_id; the current schema already has room for that via a future ADD COLUMN."
  - "schema_version table even at version 1. Establishes the migration pattern early so v0.2 can add columns idempotently without a brittle one-off boot script."
  - "WAL journal mode by default. Standard for SQLite-as-a-local-service: concurrent readers do not block the single writer, and the WAL file lives next to the database without polluting backups."
  - "Connection per operation. With WAL plus a 5 second busy timeout this scales to the desktop concurrency profile (a handful of agents writing simultaneously, a dashboard reading) without introducing a connection pool."
  - "JSON for nested fields (tool_uses, usage) rather than child tables. v0.1 reads are always whole-row; relational normalization would add migration cost without query value. Phase 08 (dashboard) renders the JSON directly."
  - "Corrupted JSON degrades to empty list/dict on read. A row with bad JSON is still listable; the user sees a trace without tool detail rather than a 500."
  - "trace_id is a UUID4 hex generated Python-side. Callers can reserve an id before persisting if a future flow needs that. The autoincrement integer stays internal."

patterns-established:
  - "Standard pragma block applied uniformly by `_connect`. Future modules that open the same database file inherit the same defaults if they go through `Database`, or replicate the block if they need a raw `sqlite3.connect`."
  - "Schema constants at module level (`SCHEMA_VERSION`, `SCHEMA_SQL`). Tests assert against them so a schema bump is a single-source-of-truth change."
  - "All test fixtures use `tmp_path` so the test suite never writes outside the isolated temp directory."

requirements-completed:
  - AGENT-02  # AgentResult instances can now be persisted into SQLite as TraceRecord rows. Wiring run_agent to auto-record happens in Phase 07/08 alongside the CLI and dashboard.

known-limitations:
  - "run_agent does NOT auto-record traces. Callers must explicitly construct a Database and invoke record_trace. Phase 07 (CLI) and Phase 08 (dashboard) ship the wiring."
  - "No retention or archival. The traces table grows without bound. v0.5 (Observability) will add retention controls and pruning."
  - "No full-text search on prompt or response. A v0.x phase can add FTS5 when the dashboard needs it."
  - "No tasks table yet. Single-turn agent invocation is the only flow in v0.1."

# Metrics
duration: 16m
completed: 2026-05-23
commit-count: 1
test-count: 12 (31 total cumulative)
lint-issues: 0
new-public-api-symbols: 2 (Database, TraceRecord)
schema-version: 1
