---
phase: 06-memory-layer-write-path
plan: "00"
subsystem: memory
tags: [memory, write, audit-trail, schema-v2, migration]

# Dependency graph
requires:
  - phase: "03-persistence-layer"
    provides: "Database class, schema_version row, idempotent init pattern"
  - phase: "05-memory-layer-read-path"
    provides: "NotesStore with list / read / search, path escape guard"
provides:
  - "NotesStore.create_note and NotesStore.append_note write paths"
  - "NoteWrite dataclass capturing one write event"
  - "Database.record_note_write and Database.list_note_writes audit primitives"
  - "create_note_tool and append_note_tool factories"
  - "Schema v2 with note_writes table and idempotent v1 to v2 migration"
affects:
  - "Phase 07 (CLI) will wire NotesStore.on_write to Database.record_note_write"
  - "Phase 08 (dashboard) will render the audit trail as a writes timeline"

# Tech tracking
tech-stack:
  added: []  # stdlib only
  patterns:
    - "Additive-only migration. CREATE TABLE IF NOT EXISTS plus a schema_version UPDATE makes the upgrade idempotent. No data migration needed."
    - "on_write callback as the bridge between the read-only memory layer and the persistence layer. Keeps both modules unaware of the other while letting the CLI / dashboard wire the audit trail."
    - "Distinct create vs append rather than a single write tool. Lets the agent be explicit about intent. Reduces the chance of accidentally clobbering content."

key-files:
  created:
    - "tests/test_notes_store_write.py, 109 lines, 12 tests"
    - "tests/test_memory_tools_write.py, 65 lines, 6 tests"
  modified:
    - "src/horus_os/storage.py, schema v2, record_note_write, list_note_writes, idempotent migration"
    - "src/horus_os/memory/notes.py, create_note, append_note, on_write hook"
    - "src/horus_os/memory/tools.py, create_note_tool, append_note_tool"
    - "src/horus_os/memory/__init__.py, re-exports"
    - "src/horus_os/types.py, NoteWrite dataclass"
    - "src/horus_os/__init__.py, public API exports"
    - "tests/test_storage.py, schema v2 assertions, migration test, write audit tests"

key-decisions:
  - "Append-or-create, no overwrite. Replace and delete are deferred to a later phase where the dashboard can add a confirm UX. The model cannot accidentally erase content in v0.1."
  - "Append newline normalization. The model can append arbitrary content without worrying about the existing file's trailing newline state. The store inserts a single newline if and only if needed."
  - "Auto-create parent directories on create_note. The model can organize notes into subdirectories without needing a separate mkdir tool."
  - "on_write callback exceptions are swallowed. A broken logger degrades observability but never blocks a write. Matches the same pattern as execute_tool_uses on_log."
  - "Migration is purely additive. Schema v1 to v2 just adds a table; no data needs to move. The migration code path is one UPDATE schema_version statement plus the IF NOT EXISTS table create."

patterns-established:
  - "Versioned schema with additive-only migrations. CREATE TABLE IF NOT EXISTS makes every forward migration safe to re-run; UPDATE schema_version tracks the current version for forward-aware tooling."
  - "Separation of mutation and audit. NotesStore mutates the filesystem; Database stores the audit row. The on_write callback is the glue that callers wire when they want both."

requirements-completed:
  - MEM-02  # Agent can append to a markdown notes folder
  - MEM-03  # Every memory write is reviewable (audit table, list_note_writes, on_write callback)

known-limitations:
  - "No delete or replace tools. v0.1 cannot remove or overwrite notes. The model has to create_note with a new path if it wants to revise existing content."
  - "Audit table content column stores the full write payload. Long writes inflate the database. v0.5 (Observability) can add truncation or compression."
  - "No transactional bundle of multiple writes. If the model writes to ten notes and the eighth raises, the first seven still apply. Bulk-write atomicity defers to a later phase if dashboards need it."

# Metrics
duration: 28m
completed: 2026-05-23
commit-count: 1
test-count: 21 (97 total cumulative)
lint-issues: 0
schema-version: 2
new-public-api-symbols: 5 (NoteWrite, create_note_tool, append_note_tool, Database.record_note_write, Database.list_note_writes)
