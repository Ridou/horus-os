# Phase 20 Plan 01 Summary

**Status:** Shipped pending CI confirmation
**Date:** 2026-05-23
**Requirements:** TEST-04, TEST-05, TEST-06

## What shipped

`scripts/install_smoke.py` grew from 8 checks to 18 checks; the v0.1
surface still runs verbatim and the v0.2 surface is now covered.
`tests/test_install_smoke.py` runs the same script under the regular
pytest matrix via `HORUS_OS_SMOKE_DATA_DIR`. The CI workflow needed no
changes; the `install-smoke` job still runs
`python scripts/install_smoke.py` with no arguments.

## Files

| File | Change | Why |
|------|--------|-----|
| `scripts/install_smoke.py` | +190 / -10 | Schema-on-disk check (version 4 + multi-agent columns), agent_profiles bootstrap check, agents list/create/show/delete round-trip, run --agent --no-stream without keys, public-surface imports + discover_adapters() |
| `tests/test_install_smoke.py` | NEW (63 lines) | Runs install_smoke.py under sys.executable with tmp_path; skips when horus-os is not on PATH |
| `.github/workflows/ci.yml` | unchanged | The script keeps the same no-args invocation; HORUS_OS_SMOKE_DATA_DIR is opt-in |

## Smoke script check list (post-Phase 20)

v0.1 surface (Phase 10):

1. `--version` prints `horus-os`
2. `--help` lists every subcommand (init, traces, serve, run, agents)
3. `init --data-dir <tmp>` populates the data dir
4. `init` refuses overwrite without `--force`
5. `init --force` reinitializes

v0.2 surface (Phase 20, on the same tmp dir):

6. `schema_version` table reads 4
7. `traces` table has `parent_trace_id` and `agent_profile_name` columns
8. `agent_profiles` is bootstrapped with the `default` row
9. `agents list` prints the default profile
10. `agents create --name smoke_test` succeeds
11. `agents show smoke_test` returns the profile body
12. `agents delete smoke_test` succeeds
13. `agent_profiles` no longer has `smoke_test` after delete
14. `traces` on empty DB prints `(no traces yet)`
15. `run "hello"` without keys exits 2 (streaming default path)
16. `run --agent default --no-stream "hello"` without keys exits 2 (buffered path)
17. `serve --help` prints `--host` and `--port`
18. `python -c "from horus_os import Adapter, AdapterContext, ToolCallEvent, discover_adapters, run_agent_stream; ..."` exits 0 and `discover_adapters()` returns a list

## Test count delta

| Suite | Before | After |
|-------|--------|-------|
| install_smoke wrapper | 0 | 1 |
| full suite | 318 | 319 |

## Verification

- `python scripts/install_smoke.py` exits 0 locally with all 18 lines
- `python -m pytest -q` reports 319 passed in ~3.5s
- `ruff check .` clean (one import-order fix auto-applied during the
  pytest wrapper write)
- `ruff format --check .` clean (71 files already formatted)
- No production code under `src/` changed
- No em-dashes / en-dashes in new files
- Commits land in three atoms: docs (plan+context), feat (smoke
  script), test (pytest wrapper), docs (this summary)

## Notable design choices

- The schema version on disk lives in the `schema_version` table that
  Phase 12 introduced. SQLite's PRAGMA `user_version` stays at 0; the
  smoke reads the table instead so it matches what migrations write.
- SQLite connections use `with sqlite3.connect(...) as conn` so the
  file handle is released before tempdir teardown. Windows tempdir
  cleanup is sensitive to lingering handles; the v0.1 script never
  opened the DB so this is new.
- The smoke accepts `HORUS_OS_SMOKE_DATA_DIR` as an optional env
  override but defaults to `tempfile.mkdtemp`. The CI call does not
  set the env, so behavior is unchanged on the dedicated job. The
  pytest wrapper sets it to `tmp_path` for isolation.
- The public-surface import smoke runs as a `sys.executable -c "..."`
  subprocess instead of importing in-process. This catches packaging
  bugs (missing module, broken re-export) on a fresh `pip install`
  rather than relying on whatever the test runner's import state is.
- The `discover_adapters()` call is the only adapter exercise in
  smoke. Binding the webhook adapter requires `HORUS_OS_WEBHOOK_SECRET`,
  which the smoke deliberately does not set; the discovery + list
  shape is what changes per-OS, not the bind path (covered in
  Phase 17 + 19 tests).

## Notable / deferred

- ROADMAP success criterion 3 (`horus-os run --agent default "hello"`
  returns a result when keys are available) is not exercised in CI.
  GitHub-hosted runners have no API keys. The smoke covers the
  no-keys error path; live-provider verification is a manual step.
- ROADMAP success criterion 4 (streaming output renders correctly in
  each OS default terminal) is covered indirectly: the streaming
  default branch error path runs through the same dispatcher as the
  happy path. A visual rendering test would require a PTY harness,
  which is out of scope here.
- No matrix change. Ubuntu, macOS, Windows by Python 3.11 and 3.12
  stays exactly as Phase 10 set it.
