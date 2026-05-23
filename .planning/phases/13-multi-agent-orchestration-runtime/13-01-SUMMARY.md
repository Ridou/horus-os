# Phase 13 Plan 01 Summary

**Status:** Shipped
**Commit:** feat(13): v4 trace schema with parent linkage and shared iteration budget
**Date:** 2026-05-23

## What shipped

The storage layer learned how to record parent/child trace links, and a
new `tools/delegation` module landed with the two primitives Plan 02
consumes. No behavior change for single-agent callers.

### Schema v4

The `traces` table gained two nullable columns and one index:

- `parent_trace_id TEXT`: coordinator's `trace_id` for sub-agent rows
- `agent_profile_name TEXT`: the profile a sub-agent ran as
- `idx_traces_parent_trace_id`: fast lookup of child rows by parent

`SCHEMA_VERSION` bumped from 3 to 4. The v3 to v4 upgrade path wraps
`ALTER TABLE` in `try/except sqlite3.OperationalError` because ADD
COLUMN is not idempotent. The parent_trace_id index is created
post-migration (outside `SCHEMA_SQL`) so v1 and v2 upgrades do not race
the column add.

### TraceRecord and Database API

- `TraceRecord` carries `parent_trace_id` and `agent_profile_name`
- `record_trace(..., parent_trace_id=..., agent_profile_name=...)`
  round-trips both
- New `Database.list_child_traces(parent_trace_id)` returns all direct
  children oldest-first

### Delegation primitives

`src/horus_os/tools/delegation.py` ships with:

- `IterationBudget(max_iterations)`: thread-safe counter shared across
  a delegation tree. `consume()` is `threading.Lock`-guarded.
- `_filter_registry(master, allowed_tools)`: returns `master` unchanged
  when `allowed_tools is None`; otherwise a new registry containing
  only the listed tools. Unknown names skip silently.

## Files touched

- `src/horus_os/storage.py`: v4 schema, migration, extended
  `record_trace`, `list_child_traces`, updated `_row_to_trace`
- `src/horus_os/tools/delegation.py`: new module
- `tests/test_storage.py`: version bumped in existing v1/v2 upgrade
  tests, four new v4 tests added
- `tests/test_delegation.py`: new file, covers budget consume + remaining
  + thread safety, and registry filtering

## Test count delta

| Surface | Before | After |
|---------|--------|-------|
| storage | 28 | 32 (+4 new v4 tests; 3 existing version assertions updated) |
| delegation | 0 | 10 |
| **full suite** | **186** | **200** |

All green: `python -m pytest -q` → 200 passed.

## Lint status

`ruff check .` and `ruff format --check .` clean across 51 files.

## Notable / deferred

- The v3 to v4 ALTER TABLE block runs in the same connection as
  `executescript(SCHEMA_SQL)`, so a fresh database goes straight to v4
  via `CREATE TABLE IF NOT EXISTS` and the migration block is a no-op.
- Index DDL for `parent_trace_id` lives outside `SCHEMA_SQL` to dodge
  the v1 to v4 column-before-index ordering hazard.
- `make_delegate_tool` deferred to Plan 13-02 by design: Plan 01 is
  the substrate, Plan 02 is the wiring.
