---
phase: 35-query-module-and-read-apis
verified: 2026-05-26T12:30:00Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
---

# Phase 35: Query module and read APIs — Verification Report

**Phase Goal:** Build observability/queries.py + 4 new /api/observability/* GET routes + extend /api/agents with rollup columns. SQLite-side NTILE(100), never aggregate-of-aggregates.

**Verified:** 2026-05-26T12:30:00Z
**Status:** VERIFICATION PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP + PLAN must_haves merged)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `queries.py` exposes 4 pure functions: `agent_totals`, `cost_by_agent`, `latency_p50_p95`, `tool_reliability`; all aggregation in SQL via NTILE(100); zero Python percentile math | VERIFIED | `__all__` at queries.py:47-53; signatures at lines 89, 196, 297, 348; `grep -rE "statistics\.(quantiles\|median\|mean)" src/horus_os/observability/` returns 0; `grep -c "NTILE(100)"` returns 4 (>=2 required) |
| 2 | 4 new GET routes `/api/observability/{cost,latency,tools,llm-calls}` accept `?since=`, default 7d, 400 on invalid | VERIFIED | api.py:321, 332, 342, 353; all have `since: str = "7d"` default; ValueError->400 conversion in all 4 handlers; `test_cost_route_400_on_invalid_window` PASSED (asserts 400 + "invalid window" in detail) |
| 3 | `/api/agents` extension: total_runs, total_cost_usd, latency_p50_ms, latency_p95_ms, uncosted_runs per agent | VERIFIED | api.py:201 calls `agent_totals(db, "7d")`; merge at lines 207-225; `test_agents_list_returns_default_after_init`, `test_agents_list_pre_v0_4_rows_render_null_cost`, `test_agents_list_mixed_v0_3_and_v0_4_rows` all PASSED |
| 4 | Percentile NULL on empty + sample_count alongside | VERIFIED | queries.py:339-340 returns `{"p50_ms": None, "p95_ms": None, "sample_count": 0}` when sample_count==0; `test_latency_p50_p95_empty_window_returns_null_not_zero` PASSED |
| 5 | `tool_reliability` honors status enum; retry_then_success NOT in error_count; never reads error_message | VERIFIED | queries.py:395-401 CASE expressions; `grep -c "error_message" queries.py` returns 0; `test_tool_reliability_retry_then_success_NOT_counted_as_error` PASSED (asserts error_count==0 with 10 success + 5 retry) |
| 6 | Anti-scope: zero touches to bus.py/persist.py/cost.py/pricing.py/pricing.json/agent.py/tools/loop.py/storage.py/pyproject.toml | VERIFIED | `git diff --stat 8e317dc..HEAD -- <forbidden files>` returns empty (zero lines); diff name-only confirms only queries.py + __init__.py + api.py + tests + SUMMARY changed |
| 7 | Full pytest green, 585+ passing | VERIFIED | `.venv/bin/python -m pytest tests/ -q` -> 585 passed in 5.06s |
| 8 | Pitfall 10 NTILE-on-raw + n>=10 contract + module docstring "never aggregate-of-aggregates" | VERIFIED | queries.py:3-7 docstring contains "never aggregate-of-aggregates"; `test_latency_p50_p95_ten_samples_all_at_100ms` PASSED (p50=p95=100); anti-pattern grep gate test PASSED |
| 9 | Pitfall 11 NULL handling: pre-v0.4 surfaces as null + uncosted_runs counter | VERIFIED | queries.py:184 returns None when total_cost is None; `test_agents_list_pre_v0_4_rows_render_null_cost` asserts total_cost_usd is None + uncosted_runs==1; `test_cost_by_agent_sum_excludes_null_and_surfaces_uncosted_runs` PASSED |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/horus_os/observability/queries.py` | NEW; parse_window + 4 query fns; >=150 lines | VERIFIED | 445 lines; all 5 public symbols in `__all__` (parse_window + 4 query fns) |
| `src/horus_os/observability/__init__.py` | re-exports 5 query functions | VERIFIED | lines 26-32 import; lines 73, 74, 76, 77, 79 in `__all__` |
| `src/horus_os/server/api.py` | 4 new routes + /api/agents extension | VERIFIED | imports at lines 46-52; 4 routes at lines 321, 332, 342, 353; /api/agents extension at lines 197-226 |
| `tests/observability/test_queries_window.py` | NEW | VERIFIED | 8 tests, all PASSED |
| `tests/observability/test_queries_agent_totals.py` | NEW | VERIFIED | 9 tests, all PASSED |
| `tests/observability/test_queries_cost_by_agent.py` | NEW | VERIFIED | 9 tests, all PASSED |
| `tests/observability/test_queries_latency_percentiles.py` | NEW; Pitfall 10 pin tests | VERIFIED | 7 tests, all PASSED including empty-window NULL contract + n=10@100ms boundary + anti-pattern grep gate |
| `tests/observability/test_queries_tool_reliability.py` | NEW; Pitfall 9 + 7 hygiene | VERIFIED | 10 tests, all PASSED including retry-then-success regression + file-content error_message hygiene assertion |
| `tests/test_server_observability_routes.py` | NEW; 4 routes integration | VERIFIED | 19 tests, all PASSED including PII canary `secret-pii-content-do-not-leak` absence check |
| `tests/test_server_agents.py` | MODIFY; 4 new assertions | VERIFIED | 18 tests, all PASSED including 4 new rollup tests |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `queries.py` | `storage.Database._connect()` | `with db._connect() as conn` | WIRED | 4 occurrences at lines 173, 275, 336, 421 |
| `api.py:/api/observability/cost` | `queries.cost_by_agent` | thin route wrapper, no SQL | WIRED | line 327: `rows = cost_by_agent(Database(cfg.db_path), since)` |
| `api.py:/api/observability/latency` | `queries.latency_p50_p95` | thin wrapper | WIRED | line 338 |
| `api.py:/api/observability/tools` | `queries.tool_reliability` | thin wrapper | WIRED | line 348 |
| `api.py:/api/agents` | `queries.agent_totals` | merge into _profile_to_dict output | WIRED | line 201: `rollups = {row["agent"]: row for row in agent_totals(db, "7d")}` |
| `queries.latency_p50_p95` | `llm_calls.latency_ms via NTILE(100) OVER (ORDER BY latency_ms)` | SQLite window function | WIRED | queries.py:325-329 CTE pattern |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| /api/observability/cost | rows | `cost_by_agent()` SELECT over windowed_traces JOIN windowed_calls | Real DB query | FLOWING |
| /api/observability/latency | latency_p50_p95 dict | NTILE(100) over llm_calls.latency_ms in window | Real DB query | FLOWING |
| /api/observability/tools | rows | `tool_reliability()` GROUP BY tool_name over tool_invocations | Real DB query | FLOWING |
| /api/observability/llm-calls | calls | explicit-column SELECT from llm_calls ORDER BY created_at DESC LIMIT 100 | Real DB query, error_message column omitted | FLOWING |
| /api/agents | agents (with rollup merge) | `agent_totals(db, "7d")` lookup merged into list_profiles() output | Real DB query | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| queries.py exposes 5 public symbols | `python -c "from horus_os.observability import parse_window, agent_totals, cost_by_agent, latency_p50_p95, tool_reliability"` | (via test re-export assertions in 5 test files, all PASSED) | PASS |
| NTILE used >=2 times | `grep -c "NTILE(100)" queries.py` | 4 | PASS |
| Zero Python percentile math | `grep -rE "statistics\.(quantiles\|median\|mean)" src/horus_os/observability/` | 0 hits | PASS |
| Zero error_message refs | `grep -c "error_message" queries.py` | 0 | PASS |
| 4 observability routes registered | `grep -c '@app\.get("/api/observability/' api.py` | 4 | PASS |
| Lint guard (no wallclock) | `python scripts/lint_no_wallclock.py` | OK (0 violations) | PASS |
| Ruff clean | `ruff check src/horus_os/observability/queries.py __init__.py src/horus_os/server/api.py` | All checks passed! | PASS |

### Probe Execution

No probe scripts declared for Phase 35. Phase 35 is a pure read-side API + query module phase. Validation lives entirely in pytest. **Status: N/A** (no `scripts/*/tests/probe-*.sh` referenced in PLAN or SUMMARY).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DASH-4-04 | 35-01-PLAN | /api/agents rollup columns (backend half); pre-v0.4 surfaces as null + uncosted_runs | SATISFIED | api.py:197-226 extension; `test_agents_list_pre_v0_4_rows_render_null_cost` PASSED; SUMMARY documents Phase 36 owns the frontend render half |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | — | — | — |

No TBD/FIXME/XXX/TODO markers in phase 35 files. No `return null` / hollow stubs. No console.log-only handlers. No hardcoded empty data in render paths. All grep checks for stub/anti-patterns return zero hits.

### Gaps Summary

No gaps. Phase 35 ships exactly what the PLAN, ROADMAP success criteria, and DASH-4-04 require:

- 4 pure query functions in `queries.py` with module-level "never aggregate-of-aggregates" docstring anchor.
- All percentile math via SQLite NTILE(100) — grep gate confirms zero `statistics.{quantiles,median,mean}` references.
- 4 new GET routes wired as thin wrappers (no SQL in route handlers except llm-calls drilldown with explicit column list omitting error_message).
- Default window 7d enforced; 400 on invalid window with "invalid window" detail substring.
- /api/agents extension merges 5 rollup fields per agent (total_runs, total_cost_usd, latency_p50_ms, latency_p95_ms, uncosted_runs); pre-v0.4 rows surface as null + uncosted_runs counter (Pitfall 11 honesty contract).
- Pitfall 9 retry-aware reliability: status enum honored; retry_then_success NOT counted as error; expected_no_result excluded from success_rate denominator.
- Pitfall 7 + 9 column hygiene: error_message column never referenced in queries.py; llm-calls drilldown route SELECTs explicit column list excluding error_message; PII canary `secret-pii-content-do-not-leak` test asserts absence from response body.
- Anti-scope perfectly held: zero diff lines in bus.py, persist.py, cost.py, pricing.py, pricing.json, agent.py, tools/loop.py, storage.py, pyproject.toml.
- Full test suite: 585 passed in 5.06s. Lint, ruff, and lint_no_wallclock all green.

Phase 35 is the read-side handoff for Phase 36 (dashboard) and Phase 37 (CLI). Both consumers can now import the 5 public symbols from `horus_os.observability` and call the 4 routes; the JSON envelope shapes are pinned in tests so the two surfaces cannot disagree about p50 or about how pre-v0.4 cost gaps render.

---

## VERIFICATION PASSED

| Dimension | Result |
|-----------|--------|
| 4 pure query functions present + JSON-serializable | PASS |
| Zero Python percentile math; NTILE(100) used 4x | PASS |
| 4 GET routes registered | PASS |
| Default window 7d + 400 on invalid | PASS |
| /api/agents extension w/ 5 rollup fields | PASS |
| Percentile NULL on empty + sample_count | PASS |
| tool_reliability honors status enum; never reads error_message | PASS |
| Anti-scope held (zero forbidden-file edits) | PASS |
| Full pytest green: 585 passed | PASS |
| Ruff clean + lint_no_wallclock OK | PASS |
| DASH-4-04 backend half satisfied | PASS |
| Pitfalls 7/9/10/11 pinned by named regression tests | PASS |

_Verified: 2026-05-26T12:30:00Z_
_Verifier: Claude (gsd-verifier)_
