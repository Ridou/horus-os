---
phase: 32-schema-migration-persistence-skeleton-v0-3-baseline
plan: "01"
subsystem: persistence
tags: [schema-migration, observability, baseline, infrastructure, v0.4]

# Dependency graph
requires:
  - phase: "31-01"  # v0.3.0 release ships the v4 schema this phase upgrades
provides:
  - "src/horus_os/storage.py at SCHEMA_VERSION = 5"
  - "src/horus_os/observability/ package (bus + events + SQLitePersister)"
  - "tests/fixtures/v0_3_database.sqlite3 (binary, 60 KB, schema v4 pinned)"
  - "tests/perf/v0_3_baseline.json (one entry at commit time; 5 more to capture)"
  - "scripts/build_v0_3_fixture.py and scripts/capture_v0_3_baseline.py"
  - "scripts/lint_no_wallclock.py + CI step + pytest wrapper (Pitfall 3 gate)"

requirements-completed:
  - STORE-01  # llm_calls table created with all 16 v0.4 columns + 3 indexes
  - STORE-02  # tool_invocations table created with all 11 v0.4 columns + 3 indexes
  - STORE-03  # four nullable rollup columns on traces (total_input_tokens etc.)
  - STORE-04  # v4 to v5 migration is additive and idempotent across multiple init() calls
  - STORE-05  # PRAGMA journal_mode=wal and synchronous=NORMAL preserved verbatim
  - BASELINE-01  # tests/perf/v0_3_baseline.json committed before Phase 33 starts
  - TEST-11  # v0.3 fixture migration test, idempotency test, pragma readback test
  - MIG-04  # additive v4 to v5 migration with old usage JSON blob preserved

# Tech stack
tech-stack:
  added: []
  patterns:
    - "ALTER TABLE ADD COLUMN wrapped in try/except sqlite3.OperationalError for idempotency (mirrors storage.py:137-146)"
    - "ObservationBus subscribe/publish with per-subscriber try/except BaseException (mirrors tools/loop.py:_call_logger)"
    - "All-or-nothing aggregate (CASE on COUNT vs COUNT(col)) to force NULL when any contributing row is NULL (Pitfall 5)"
    - "stdlib-only scripts (no new pyproject.toml dependencies)"

# Key files
key-files:
  created:
    - src/horus_os/observability/__init__.py
    - src/horus_os/observability/bus.py
    - src/horus_os/observability/persist.py
    - scripts/build_v0_3_fixture.py
    - scripts/capture_v0_3_baseline.py
    - scripts/lint_no_wallclock.py
    - tests/observability/__init__.py
    - tests/observability/test_bus.py
    - tests/observability/test_persister.py
    - tests/fixtures/__init__.py
    - tests/fixtures/v0_3_database.sqlite3
    - tests/perf/__init__.py
    - tests/perf/v0_3_baseline.json
    - tests/test_lint_no_wallclock.py
  modified:
    - src/horus_os/storage.py
    - tests/test_storage.py
    - .github/workflows/ci.yml
    - scripts/install_smoke.py
    - tests/test_install_smoke.py
    - tests/test_e2e_dashboard_composition.py

# Metrics
duration: 13m
completed: 2026-05-26
total-tests: 459 passed
commits: 7
---

# Phase 32 Plan 01 Summary: schema v5 migration, persistence skeleton, v0.3 baseline

## What shipped

Pure infrastructure phase. Seven atomic commits landed the substrate every
Phase 33-38 plan needs before it can wire capture sites, compute costs,
query rollups, or export OTLP spans.

1. `src/horus_os/storage.py` at `SCHEMA_VERSION = 5`. Two new tables
   (`llm_calls` 16 cols + 3 indexes, `tool_invocations` 11 cols + 3
   indexes) and four nullable rollup columns on `traces`
   (`total_input_tokens`, `total_output_tokens`, `total_cost_usd`,
   `total_duration_ms`). The v4 to v5 migration block in `Database.init()`
   uses ALTER TABLE ADD COLUMN wrapped in `try/except sqlite3.OperationalError`,
   mirroring the v3 to v4 idempotent pattern at storage.py:137-146.
2. `src/horus_os/observability/` package with `bus.py` (ObservationBus,
   ObservationEvent base, LLMCallEvent, ToolCallEvent, RunEndEvent) and
   `persist.py` (SQLitePersister). Bus dispatch is synchronous; each
   subscriber call is wrapped in `try/except BaseException` so one broken
   subscriber cannot starve the rest.
3. `tests/fixtures/v0_3_database.sqlite3`: 60 KB binary fixture pinned at
   schema v4 with two synthetic traces (one carrying a non-trivial usage
   JSON blob), one note_writes row, one agent_profiles row. Synthetic
   data only, no PII. Regenerable bit-for-bit via
   `scripts/build_v0_3_fixture.py`.
4. `tests/perf/v0_3_baseline.json`: BASELINE-01 artifact seeded with one
   entry for the developer's local environment. Five more (os, python)
   combos to capture before Phase 33 begins.
5. `scripts/capture_v0_3_baseline.py`: stdlib-only baseline harness.
   Monkey-patches `agent._new_conversation` inside the script's own
   process, runs a three-iteration loop N=20 times via
   `time.perf_counter()`, merges the median into the JSON keyed on
   `(os, python)`. Idempotent across re-runs.
6. `scripts/lint_no_wallclock.py` + `tests/test_lint_no_wallclock.py` +
   one new CI step `time.time() lint gate (Pitfall 3)`. The scanner
   walks observability/, agent.py, tools/loop.py; comments and
   triple-quoted docstring regions are exempt so Pitfall 4 contract
   docstrings (which name the forbidden literal) do not self-trip.
7. This SUMMARY plus the three Rule 1 schema-bump fixes
   (`install_smoke.py`, `test_install_smoke.py`,
   `test_e2e_dashboard_composition.py`).

## Requirements satisfied

- **STORE-01**: `llm_calls` table exists with 16 v0.4 columns and three
  indexes (`idx_llm_calls_trace_id`, `idx_llm_calls_created_at`,
  `idx_llm_calls_model`). Verified by `test_v5_init_is_idempotent` and
  `test_schema_v4_database_upgrades_to_v5`.
- **STORE-02**: `tool_invocations` table exists with 11 v0.4 columns and
  three indexes (`idx_tool_invocations_trace_id`,
  `idx_tool_invocations_tool_name`, `idx_tool_invocations_created_at`).
  Same tests cover.
- **STORE-03**: four nullable rollup columns on `traces`. Verified by
  `test_schema_v4_database_upgrades_to_v5` asserting pre-v0.4 rows have
  NULL on the new columns (Pitfall 11 substrate).
- **STORE-04**: migration is additive and idempotent. Verified by
  `test_v5_init_is_idempotent` (three init() calls leave the database in
  a stable v5 state) plus the v3 to v4 to v5 chain in
  `test_schema_v1_database_upgrades_to_current` (still green at v5).
- **STORE-05**: PRAGMAs survive `init()`. Verified by
  `test_pragmas_read_back_correctly`: `journal_mode=wal` persists at the
  file level, `synchronous=NORMAL` (integer 1, never 2 FULL or 0 OFF) on
  connections opened via the same PRAGMA dance.
- **BASELINE-01**: `tests/perf/v0_3_baseline.json` committed before
  Phase 33 starts. Script is idempotent; remaining (os, python) combos
  can be captured on each target machine without disturbing existing
  entries.
- **TEST-11**: three new tests landed in `test_storage.py`
  (schema_v4_to_v5 migration, v5_init_is_idempotent, pragmas_read_back).
  Total storage tests at end of phase: 34 (up from 31).
- **MIG-04**: v4 to v5 migration preserves the old `traces.usage` JSON
  blob byte-for-byte. Verified by `test_schema_v4_database_upgrades_to_v5`.

## ROADMAP Success Criteria

- [x] Fresh-DB `init()` creates `llm_calls`, `tool_invocations`, and the
  four nullable rollup columns on `traces`; double-init is a no-op
  (idempotent). [Task 1 + Task 4 test_v5_init_is_idempotent]
- [x] `tests/fixtures/v0_3_database.sqlite3` upgrades cleanly through
  `Database.init()`: new tables and columns exist, old `traces.usage`
  JSON blob still reads, pre-v0.4 rows have NULL on the four new
  columns. [Task 4 test_schema_v4_database_upgrades_to_v5]
- [x] `PRAGMA journal_mode` reads back as `wal`, `PRAGMA synchronous`
  reads back as 1 (NORMAL), never 2 (FULL). [Task 4
  test_pragmas_read_back_correctly]
- [x] `tests/perf/v0_3_baseline.json` committed with at least one
  (os, python) entry populated. [Task 5]
- [x] Unit tests publish synthetic `ObservationEvent`s directly to
  `ObservationBus`, `SQLitePersister` writes rows into the right
  tables, and no runner code (agent.py, tools/loop.py) is touched.
  [Task 3 tests/observability/test_persister.py +
  test_run_end_rolls_up_traces_columns + grep gate proving no
  imports from horus_os.agent or horus_os.tools]

## Pitfalls guarded

- **Pitfall 3** (wall-clock vs perf_counter): `scripts/lint_no_wallclock.py`
  scans observability/, agent.py, tools/loop.py. Exempts comments and
  triple-quoted docstring regions so Pitfall 4 contract docstrings can
  spell out the forbidden literal without self-tripping. Wired into the
  unit-test job and into `.github/workflows/ci.yml`. Landed in commit
  `39c73c3`. Also enforced in `_insert_llm_call` and
  `_insert_tool_invocation` via `assert event.latency_ms >= 0`
  (rejected with AssertionError, proven by `test_negative_latency_rejects`).
- **Pitfall 5** (NULL is honest, zero is a lie): `_rollup_trace` uses an
  all-or-nothing aggregate (`CASE WHEN COUNT(*) > COUNT(cost_usd) THEN
  NULL ELSE SUM(cost_usd) END`) so when any contributing llm_calls row
  has `cost_usd` NULL, the rollup stays NULL. Verified by
  `test_run_end_rolls_up_traces_columns` (mixed-NULL contributors, row
  asserted as None not 0.0). Landed in commit `0e265f0`.
- **Pitfall 8** (PRAGMA discipline + indexes): existing
  `Database._connect` PRAGMAs preserved verbatim. New indexes on
  `llm_calls` and `tool_invocations` are the minimum useful set
  (`trace_id`, `created_at DESC`, and one secondary). Verified by
  `test_pragmas_read_back_correctly`. Landed in commit `c0d7c6e`.
- **Pitfall 11** (additive-only schema contract): four new traces
  columns are nullable with no DEFAULT; no DROP or RENAME on any
  existing column; `traces.usage` JSON blob preserved forever. Verified
  by `test_schema_v4_database_upgrades_to_v5` (NULL on pre-v0.4 rows +
  old usage JSON still reads). Landed in commit `c0d7c6e`.

## What is NOT yet wired

Phase 32 ships infrastructure only. The bus is **not** subscribed to by
`agent.py` or `tools/loop.py`. No events flow yet. No cost annotation
runs. Phase 33 will wire capture sites in `run_agent_loop` (LLM_CALL and
RUN_END) and `_execute_one` (TOOL_CALL). Phase 34 will add the
CostAnnotator subscriber that populates `cost_usd` and `pricing_missing`
before the persister sees the event.

## Deviations from plan

All four deviations are Rule 1 auto-fixes (bugs the plan introduces by
bumping `SCHEMA_VERSION`; updating the matching assertions is mandatory
follow-up, not new scope).

1. **[Rule 1 - Bug] Updated four pre-existing `assert version == 4` lines
   in `tests/test_storage.py` to `assert version == 5`.** Found during
   Task 1 verification. Plan bumps the schema; matching test assertions
   must move in lockstep. Committed inside Task 1 (c0d7c6e).
2. **[Rule 1 - Bug] Updated `assert version == 4` in
   `tests/test_e2e_dashboard_composition.py` to `5`.** Found during the
   Task 7 full-suite run. Same root cause: pre-existing test pins the
   schema version. Committed in this final docs commit.
3. **[Rule 1 - Bug] Updated `SCHEMA_VERSION_EXPECTED = 4` to `5` in
   `scripts/install_smoke.py`.** Found during the Task 7 full-suite
   run. The install-smoke script asserts the on-disk schema matches the
   shipped version. Committed in this final docs commit.
4. **[Rule 1 - Bug] Updated `assert "schema_version==4" in proc.stdout`
   to `"schema_version==5"` in `tests/test_install_smoke.py`.** Same
   root cause as #3. Committed in this final docs commit.

Two additional minor deviations during implementation:

5. **[Rule 1 - Bug] SQL `SUM` skips NULLs; plan's "bare `SUM(cost_usd)`
   preserves NULL when any contributing row is NULL" is incorrect about
   SQL semantics.** Replaced with an all-or-nothing CASE
   (`WHEN COUNT(*) > COUNT(cost_usd) THEN NULL`). The plan's stated
   intent (Pitfall 5: never lie about pricing-missing rows) is honored;
   only the SQL expression changed. Test
   `test_run_end_rolls_up_traces_columns` proves the contract holds.
6. **[Rule 1 - Bug] The Task 2 acceptance criterion
   `grep -v '^[[:space:]]*#' | grep -c "time.time()"` returns 0 conflicts
   with the same Task 2's explicit mandate to include the Pitfall 4
   docstring containing the literal `time.time()` text.** The grep
   counts docstring lines as non-comment, which the plan did not
   account for. The mandated docstring was kept verbatim per the
   explicit `<observation_event_canonical>` block, and
   `scripts/lint_no_wallclock.py` was designed to exempt triple-quoted
   docstring regions so the gate stays useful (catches code, not
   prose). The gate exits 0 at commit time on the whole repo.

## Authentication gates

None encountered. Pure local infrastructure phase.

## Test counts

- Before Phase 32: 447 (per `.planning/STATE.md` Prior Milestones).
- After Phase 32: **459 passed, 0 failed, 0 skipped** (12 new tests:
  3 storage migration/pragma tests, 4 bus tests, 4 persister tests, 1
  lint gate wrapper test).

## Out of scope (deliberate)

- **`src/horus_os/agent.py` capture sites**: Phase 33.
- **`src/horus_os/tools/loop.py` capture sites**: Phase 33.
- **`src/horus_os/server/api.py` SSE branch fix**: Phase 33.
- **CostAnnotator subscriber + pricing.json**: Phase 34.
- **Per-OS baseline entries for linux/win32 and Python 3.11**: captured
  by re-running `scripts/capture_v0_3_baseline.py` on each target before
  Phase 33 begins.

## Process notes

- Ruff is clean across the repo (101 files formatted).
- `lint_no_wallclock` is clean across the three watched paths.
- The negative test for the lint gate was verified locally (injected
  `_ = time.time()` into `bus.py`, gate exited 1 with the offending
  file:line on stderr; reverted before commit). No violation reached
  the index.
- The v0.3 fixture was regenerated twice and verified bit-identical via
  SHA-256.

## BASELINE-01 capture status

| OS | Python | captured | median_3_iteration_loop_ms |
|----|--------|----------|----------------------------|
| darwin | 3.12 | yes (2026-05-26) | 0.005 |
| darwin | 3.11 | no | (capture on macOS 3.11 target before Phase 33) |
| linux | 3.11 | no | (capture on Ubuntu 3.11 target before Phase 33) |
| linux | 3.12 | no | (capture on Ubuntu 3.12 target before Phase 33) |
| win32 | 3.11 | no | (capture on Windows 3.11 target before Phase 33) |
| win32 | 3.12 | no | (capture on Windows 3.12 target before Phase 33) |

## Self-Check

Verified after writing this SUMMARY:

- All seven plan commits exist with the required `feat(32)`,
  `test(32)`, `chore(32)`, `docs(32)` prefixes.
- All committed files in the `key-files.created` list above exist on
  disk.
- All committed files in the `key-files.modified` list above exist on
  disk.
- `pytest -x -q` exits 0 with 459 passed.
- `ruff check .` exits 0.
- `ruff format --check .` exits 0.
- `python scripts/lint_no_wallclock.py` exits 0.
- No modifications to `.planning/STATE.md` or `.planning/ROADMAP.md`
  (worktree mode; orchestrator owns those writes).

## Self-Check: PASSED
