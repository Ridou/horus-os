---
phase: 40-v0-5-baseline-artifact
plan: "01"
subsystem: performance-baseline
tags: [baseline, observability, infrastructure, v0.5, BASELINE-02]

# Dependency graph
requires:
  - phase: "39"  # v0.4.0 shipped; observability surface and v4 schema in place
provides:
  - "scripts/capture_v0_4_baseline.py (stdlib-only capture harness, perf_counter_ns)"
  - "tests/perf/v0_4_baseline.json (1 populated darwin row + 3 placeholders)"
  - "tests/perf/test_v0_4_baseline.py (schema-shape contract, 3 tests)"

requirements-completed:
  - BASELINE-02  # tests/perf/v0_4_baseline.json captures v0.4 cold-start + zero-plugin discovery overhead before Phase 42 begins

# Tech stack
tech-stack:
  added: []
  patterns:
    - "stdlib-only capture script (no new pyproject.toml dependencies)"
    - "time.perf_counter_ns exclusively for all wall-clock measurement (Pitfall 3 social discipline carried into scripts/)"
    - "subprocess.run with list-form args + explicit timeout for cold-start metrics (T-40-06 no shell expansion)"
    - "sys.modules pop loop before each in-process discover_adapters() sample so the re-import + entry-points walk is measured cold"
    - "idempotent JSON merge keyed on (os, python) so multi-host capture diffs cleanly"

# Key files
key-files:
  created:
    - scripts/capture_v0_4_baseline.py
    - tests/perf/v0_4_baseline.json
    - tests/perf/test_v0_4_baseline.py
    - .planning/phases/40-v0-5-baseline-artifact/40-01-SUMMARY.md
  modified: []

# Metrics
duration: ~10m
completed: 2026-05-26
total-tests: 721 passed (3 new)
commits: 3
---

# Phase 40 Plan 01 Summary: v0.5 baseline artifact (BASELINE-02)

## One-line description

Pure infrastructure phase. Lands `scripts/capture_v0_4_baseline.py` (stdlib-only, perf_counter_ns) and seeds `tests/perf/v0_4_baseline.json` with one captured darwin row plus three CI-backfill placeholders so Phase 42's TEST-18 cold-start <100ms benchmark has a pinned reference.

## What shipped

Three atomic commits. No `src/horus_os/` runtime code touched.

1. **`feat(40): scripts/capture_v0_4_baseline.py`**. Mirror of `scripts/capture_v0_3_baseline.py`. Stdlib only. Four measurement helpers, each takes the median of N=20 samples and rounds to 3 decimal places:
   - `_capture_wall_clock_ms()`: subprocess `python -c "from horus_os.server.api import create_app; create_app()"` (cold)
   - `_capture_agent_loop_3_iter_ms()`: in-process 3-iteration stub-provider loop (v0.3 parity for METRIC-05 trend continuity)
   - `_capture_cold_import_ms()`: subprocess `python -c "import horus_os.adapters"` (fresh interpreter per sample)
   - `_capture_entry_points_discovery_ms()`: in-process `discover_adapters()` with `sys.modules` clearing between samples
   
   All four use `time.perf_counter_ns()` exclusively; the script contains no `time.time()` or `time.perf_counter()` callers. Idempotent on re-run: replaces the existing `(os, python)` entry in place.

2. **`chore(40): tests/perf/v0_4_baseline.json`**. Output of running the capture script on the maintainer's darwin / Python 3.12 machine, plus three placeholder rows for `(linux, 3.11)`, `(linux, 3.12)`, `(win32, 3.11)` so CI runners can spot which combos still need backfill before Phase 42 begins.

3. **`test(40): tests/perf/test_v0_4_baseline.py + Phase 40 SUMMARY`**. Three stdlib-only pytest functions guarding the schema contract: every row has the nine canonical fields with no extras; at least one row is fully populated with positive numeric measurements; no duplicate `(os, python)` keys. Plus this SUMMARY.

## Populated darwin row

Captured 2026-05-26 on macOS arm64 / Python 3.12.7, N=20 samples per metric, median rounded to 3 decimal places.

| Metric | Value (ms) | What it measures |
|--------|-----------|------------------|
| `wall_clock_ms` | 339.261 | Cold subprocess `create_app()` startup (headline BASELINE-02 number) |
| `agent_loop_3_iter_ms` | 0.034 | In-process 3-iteration agent loop against stub provider (v0.3 parity) |
| `cold_import_ms` | 95.193 | Cold subprocess `import horus_os.adapters` |
| `entry_points_discovery_ms` | 1.909 | In-process `discover_adapters()` with sys.modules clearing |

Captured at `2026-05-26T11:08:23.714629Z`.

## Requirements satisfied

- **BASELINE-02** (REQUIREMENTS.md line 358): `tests/perf/v0_4_baseline.json` artifact captures v0.4 cold-start time + discovery overhead with zero plugins; committed before Phase 42 discovery work lands. Evidence: file exists at `tests/perf/v0_4_baseline.json` carrying the populated darwin row plus three placeholder rows; `tests/perf/test_v0_4_baseline.py` guards the schema; Phase 42's TEST-18 benchmark reads the row matching the active CI runner.

## ROADMAP Phase 40 Success Criteria

- [x] **1.** `tests/perf/v0_4_baseline.json` committed before any Phase 42 discovery work lands; captures wall-clock cold-start time for `from horus_os.server.api import create_app; create_app()` on the maintainer's (darwin, py3.12) target. Linux 3.11, linux 3.12, and win32 3.11 placeholder rows committed for CI backfill before Phase 42 starts.
- [x] **2.** Baseline captures discovery overhead with zero installed plugins (no entry points in the future `horus_os.plugins` group; the v0.4-era `horus_os.adapters` group is what `discover_adapters()` walks today). Schema carries `os`, `python`, `horus_os_version`, `wall_clock_ms`, `agent_loop_3_iter_ms`, `cold_import_ms`, `entry_points_discovery_ms`, `n_samples`, `captured_at` per row.
- [x] **3.** Reproducible capture: `scripts/capture_v0_4_baseline.py` is the same fixture-script pattern v0.3 Phase 32 set; runs on any (os, python) target without modification; re-running on the same target replaces the row in place so a re-capture diffs cleanly.
- [x] **4.** No runtime code touched. Only `scripts/capture_v0_4_baseline.py` (capture harness), `tests/perf/v0_4_baseline.json` (artifact), `tests/perf/test_v0_4_baseline.py` (schema gate), and this SUMMARY. `pip install -e .` continues to work unchanged; no `pyproject.toml` edits.

## BASELINE-02 capture status

| OS | Python | Status | wall_clock_ms |
|----|--------|--------|---------------|
| darwin | 3.12 | populated (2026-05-26) | 339.261 |
| darwin | 3.11 | not committed | (optional) |
| linux | 3.11 | placeholder | (capture on Ubuntu 3.11 CI runner before Phase 42) |
| linux | 3.12 | placeholder | (capture on Ubuntu 3.12 CI runner before Phase 42) |
| win32 | 3.11 | placeholder | (capture on Windows 3.11 CI runner before Phase 42) |
| win32 | 3.12 | not committed | (optional) |

The three placeholder rows mark which CI targets still owe a capture before Phase 42 ships. The schema-shape test tolerates placeholders (captured_at == "placeholder" + null measurements) while requiring at minimum one populated row.

## Deviations from plan

None of substance. Two minor self-corrections during Task 1:

1. The script's module docstring originally read "exclusively uses time.perf_counter_ns(); the script never calls time.time() or time.perf_counter()" verbatim. The acceptance criterion `grep -v '^[[:space:]]*#' | grep -c "time.time()"` counts docstring lines as non-comment (matches the same Phase 32 deviation #6 in 32-01-SUMMARY.md). Rephrased the docstring to "the nanosecond perf counter" and "calendar-time or seconds-resolution timers" so the literal substrings stay out of the file while the prose stays clear.

2. The plan's `<v0_4_baseline_json_canonical>` block describes the discovery walk as "zero installed adapter packages on the maintainer's machine this returns []". In practice the v0.4 codebase declares six adapter entry points in `pyproject.toml` (`webhook`, `discord`, `slack`, `email`, `calendar`, `otel`) so `discover_adapters()` returns 6, not 0. The `entry_points_discovery_ms` metric captures the v0.4 floor with the 6 built-in adapters present; Phase 42's `discover_plugins()` walk against the future `horus_os.plugins` group is what stays bounded at zero plugins. The semantic "zero-plugin discovery floor" still holds (no third-party plugins installed); the wording in the plan is slightly imprecise about which entry-points group it refers to. No code change needed.

## What is NOT yet wired

Phase 40 ships infrastructure only. The artifact sits in `tests/perf/`; nothing reads it yet. Phase 42 (`/gsd-plan-phase 42`) introduces `plugins/discovery.py` and the TEST-18 cold-start benchmark that will load the matching row from `v0_4_baseline.json` and assert the live `discover_plugins() + load + validate` pass stays within 100ms of the pinned `wall_clock_ms`.

## Authentication gates

None. Pure local infrastructure phase.

## Test counts

- Before Phase 40: 718 passed (per the v0.4.0 release summary, 459 from Phase 32 + 8 phases of v0.4 work).
- After Phase 40: **721 passed, 0 failed, 0 skipped** (three new tests in `tests/perf/test_v0_4_baseline.py`).
- `ruff check .` clean across the repo.
- `python scripts/lint_no_wallclock.py` exits 0 (the watched `src/horus_os` paths are untouched).

## Out of scope (deliberate)

- **Live capture on linux 3.11 / linux 3.12 / win32 3.11**: deferred to CI runners; placeholder rows mark the backfill ledger.
- **Phase 41 schema substrate** (PluginSpec, MANIFEST_V1_SCHEMA, plugins/api.py, v5 to v6 migration): next phase, blocked-on Phase 40 per ROADMAP execution order `40 -> 41 -> 42`.
- **Phase 42 discovery + loading + failure isolation + TEST-18 benchmark**: consumes the artifact this phase pins; do not start until linux/win32 placeholder rows have at least one CI capture each.

## Process notes

- Capture wall clock on darwin py3.12: about 2 minutes total (4 metrics × 20 samples; the subprocess metrics dominate).
- Idempotency live-checked: re-running `python scripts/capture_v0_4_baseline.py` after the chore commit updates the maintainer's row in place without duplicating. The post-rerun floating delta is expected on real hardware and is left uncommitted (the original Step A capture is what ships).
- No SSE branch or runtime code changed; the Phase 33 lint gate (`scripts/lint_no_wallclock.py`) sees zero file changes within its watched scope.

## Phase 41 unblocked

Per ROADMAP execution order: `40 -> 41 -> 42 -> ...`. Phase 41 (Manifest schema, public API, persistence migration) depends_on Phase 40 (the baseline artifact). With BASELINE-02 satisfied and the three commits on local main, Phase 41 can be opened with `/gsd-plan-phase 41` whenever the maintainer is ready.

## Atomic commit ledger

1. `feat(40): scripts/capture_v0_4_baseline.py. v0.4 cold-start + zero-plugin discovery capture (BASELINE-02)`. `faeace2`
2. `chore(40): tests/perf/v0_4_baseline.json. seeded baseline (1 darwin row + 3 placeholders)`. `ca30c54`
3. `test(40): tests/perf/test_v0_4_baseline.py + 40-01-SUMMARY.md`. (this commit)

## Self-Check

Verified after writing this SUMMARY:

- All three plan commits exist on local main with the required `feat(40)`, `chore(40)`, `test(40)` prefixes (see ledger above; third hash filled in by the commit producing this SUMMARY).
- `tests/perf/v0_4_baseline.json` exists, parses, has 4 rows, one populated, three placeholder.
- `scripts/capture_v0_4_baseline.py` exists, ruff clean, ast.parse clean, no `time.time()` or `time.perf_counter()` calls.
- `tests/perf/test_v0_4_baseline.py` exists, ruff clean, three tests pass.
- `pytest -x -q` exits 0 with 721 passed.
- `ruff check .` exits 0.
- `python scripts/lint_no_wallclock.py` exits 0.
- No modifications to `src/horus_os/`, `.planning/STATE.md`, `.planning/ROADMAP.md`, or `pyproject.toml`.
