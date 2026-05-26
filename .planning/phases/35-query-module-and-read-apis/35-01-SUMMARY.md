---
phase: 35-query-module-and-read-apis
plan: "01"
subsystem: observability
tags: [queries, read-api, ntile, percentiles, observability, v0.4, dash-4-04]

# Dependency graph
requires:
  - phase: "33-01"  # ObservationBus singleton + SQLitePersister capture sites + llm_calls/tool_invocations
  - phase: "34-01"  # cost_usd populated for known models; pricing_missing flag; all-or-nothing rollup
provides:
  - "src/horus_os/observability/queries.py: parse_window + agent_totals + cost_by_agent + latency_p50_p95 + tool_reliability pure functions"
  - "src/horus_os/observability/__init__.py: queries module re-exports added to __all__"
  - "src/horus_os/server/api.py: four new /api/observability/{cost,latency,tools,llm-calls} GET routes"
  - "src/horus_os/server/api.py: /api/agents extended with total_runs, total_cost_usd, latency_p50_ms, latency_p95_ms, uncosted_runs per agent (DASH-4-04 backend half)"

requirements-completed:
  - DASH-4-04  # /api/agents rollup columns; pre-v0.4 rows surface as total_cost_usd null + uncosted_runs counter

# Tech stack
tech-stack:
  added: []
  patterns:
    - "SQL-side aggregation via SQLite NTILE(100) OVER (ORDER BY latency_ms); never Python statistics percentile helpers (Pitfall 10 anti-pattern guard, grep-enforced)"
    - "Empty-window NULL contract: percentile fields return Python None, JSON null, NEVER 0 (Pitfall 10 line 272)"
    - "Sample count surfaced alongside p50/p95 so callers apply the n>=10 render rule (Pitfall 10)"
    - "Pre-v0.4 NULL handling: SUM excludes NULL rows; uncosted_runs counter surfaces them separately so the dashboard explains missing dollars (Pitfall 11)"
    - "Retry-aware reliability: status enum {success, error, retry_then_success, expected_no_result}; retry_then_success NOT counted as error; expected_no_result excluded from success_rate denominator (Pitfall 9)"
    - "Column hygiene: the text-content error column on llm_calls and tool_invocations is NEVER referenced in queries.py and is DELIBERATELY omitted from the llm-calls drilldown route's SELECT (Pitfall 7 + Pitfall 9)"
    - "Window parser ValueError -> HTTPException 400 conversion at the route boundary; parameterized SQL placeholders for all filters (defense against tampering)"
    - "Python round(value, 6) at the boundary (NOT SQLite ROUND) for cross-OS deterministic 6-decimal cost rounding"
    - "stdlib only (sqlite3, datetime, pathlib, typing); no new pyproject.toml dependencies"

# Key files
key-files:
  created:
    - src/horus_os/observability/queries.py
    - tests/observability/test_queries_window.py
    - tests/observability/test_queries_agent_totals.py
    - tests/observability/test_queries_cost_by_agent.py
    - tests/observability/test_queries_latency_percentiles.py
    - tests/observability/test_queries_tool_reliability.py
    - tests/test_server_observability_routes.py
    - .planning/phases/35-query-module-and-read-apis/35-01-SUMMARY.md
  modified:
    - src/horus_os/observability/__init__.py
    - src/horus_os/server/api.py
    - tests/test_server_agents.py

# Metrics
duration: 90m
completed: 2026-05-26
total-tests: 585 passed
commits: 13
---

# Phase 35 Plan 01 Summary: query module and read APIs

## What shipped

Thirteen atomic commits ship the single read-side query module the Phase 36 dashboard and Phase 37 CLI will both consume so the two surfaces cannot disagree about what a number means. All percentile math lives in SQLite via NTILE(100); a grep gate proves zero Python percentile helper references in `queries.py`. Pre-v0.4 traces (total_cost_usd NULL on rollup columns from before Phase 34) surface as `total_cost_usd: null` plus a separate `uncosted_runs: N` counter so the dashboard explains missing dollars instead of hiding them as zero. Retry-aware tool reliability honors the four-value status enum so retry_then_success rows do NOT inflate error_count (the exact bug Pitfall 9 prevents). The text-content error column on llm_calls and tool_invocations stays sealed inside the persister write path; the queries module never reads it and the llm-calls drilldown route omits it from its explicit SELECT column list.

| Commit  | Type        | Title                                                                     |
| ------- | ----------- | ------------------------------------------------------------------------- |
| a0cd831 | test(35-01) | Task 1 RED: failing tests for parse_window + agent_totals                 |
| 048c4b2 | feat(35-01) | Task 1 GREEN: queries.py skeleton + parse_window + agent_totals           |
| e6a6316 | test(35-01) | Task 2 RED: failing tests for cost_by_agent                               |
| dea5f9f | feat(35-01) | Task 2 GREEN: cost_by_agent with cache tokens + uncosted_runs             |
| 49337f8 | test(35-01) | Task 3 RED: failing tests for latency_p50_p95 + Pitfall 10                |
| f51b13b | feat(35-01) | Task 3 GREEN: latency_p50_p95 with NTILE + null-on-empty contract         |
| cfec6e7 | test(35-01) | Task 4 RED: failing tests for tool_reliability + Pitfalls 7/9             |
| 9d02aaf | feat(35-01) | Task 4 GREEN: tool_reliability with retry-aware status enum (Pitfall 9)   |
| c8aabb6 | test(35-01) | Task 5 RED: failing integration tests for /api/observability/* routes     |
| d0089e2 | feat(35-01) | Task 5 GREEN: four /api/observability/* GET routes                        |
| 7b4b427 | test(35-01) | Task 6 RED: failing tests for /api/agents rollup extension (DASH-4-04)    |
| cbfc4f7 | feat(35-01) | Task 6 GREEN: /api/agents extension with rollup columns (DASH-4-04)       |
| 53d6203 | style(35-01)| apply ruff format to Phase 35 files                                       |

## Requirements satisfied

- **DASH-4-04** (`/api/agents` rollup; pre-v0.4 surface): Task 6. The list-all-profiles route gains five new per-agent fields sourced from `agent_totals(db, '7d')`: `total_runs`, `total_cost_usd`, `latency_p50_ms`, `latency_p95_ms`, `uncosted_runs`. Pre-v0.4 rows (every contributing trace has `total_cost_usd IS NULL`) surface as `total_cost_usd: null` and `uncosted_runs: N`, never as zero dollars. Pinned by `tests/test_server_agents.py::test_agents_list_pre_v0_4_rows_render_null_cost` (synthetic NULL trace -> total_runs=1, total_cost_usd is None, uncosted_runs=1) and `::test_agents_list_mixed_v0_3_and_v0_4_rows` (0.005 + NULL -> total_cost_usd=0.005, uncosted_runs=1, SUM excludes NULL). The frontend render half lands in Phase 36.

## ROADMAP Success Criteria

- [x] `observability/queries.py` exposes `agent_totals(window)`, `cost_by_agent(window)`, `latency_p50_p95(window)`, `tool_reliability(window)` as pure functions returning JSON-serializable dicts; all aggregation in SQL via `NTILE(100) OVER (...)`. Grep confirms zero `statistics.quantiles|median|mean` references in queries.py. [Tasks 1-4]
- [x] Four new GET routes `/api/observability/{cost,latency,tools,llm-calls}` accept `?since=24h|7d|30d` plus generic `Nh`/`Nd`; default window `7d` when omitted; invalid window returns 400 with `invalid window:` in the detail. [Task 5]
- [x] Existing `/api/agents` route gains `total_runs`, `total_cost_usd`, `latency_p50_ms`, `latency_p95_ms`, `uncosted_runs` per agent. Pre-v0.4 rows surface as `null` + `uncosted_runs` counter (DASH-4-04 backend; Pitfall 11). [Task 6]
- [x] Percentile queries return `None` (JSON null) for empty windows; `sample_count` returned alongside `p50_ms`/`p95_ms` for the caller-side n>=10 render rule. [Tasks 1, 3]
- [x] `tool_reliability` honors the status enum: `retry_then_success` rows do NOT count toward `error_count`; query never reads the text-content error column (Pitfall 9). Grep confirms zero `error_message` substrings in queries.py. [Task 4]

## Pitfalls guarded

| Pitfall | Owner Task | Pin Test |
|---------|-----------|----------|
| Pitfall 9 (retry-aware reliability; never read error text column) | Task 4 | `tests/observability/test_queries_tool_reliability.py::test_tool_reliability_retry_then_success_NOT_counted_as_error` (10 success + 5 retry -> error_count=0); `::test_queries_py_never_references_error_message_column` (file-content substring assertion) |
| Pitfall 10 (small-sample percentile + NULL not 0 on empty) | Tasks 1, 3 | `tests/observability/test_queries_latency_percentiles.py::test_latency_p50_p95_empty_window_returns_null_not_zero`; `::test_latency_p50_p95_ten_samples_all_at_100ms` (boundary line 267); `::test_queries_module_does_not_use_python_percentile_helpers` (anti-pattern grep gate); module docstring contains "never aggregate-of-aggregates" |
| Pitfall 11 (pre-v0.4 NULL handling) | Tasks 1, 2, 6 | `tests/observability/test_queries_agent_totals.py::test_agent_totals_cost_sum_excludes_null_rows_and_surfaces_uncosted_counter`; `tests/observability/test_queries_cost_by_agent.py::test_cost_by_agent_sum_excludes_null_and_surfaces_uncosted_runs`; `tests/test_server_agents.py::test_agents_list_pre_v0_4_rows_render_null_cost` |
| Pitfall 7 (text-content error column never leaves persister) | Tasks 4, 5 | `tests/observability/test_queries_tool_reliability.py::test_queries_py_never_references_error_message_column` (file-content); `tests/test_server_observability_routes.py::test_llm_calls_route_excludes_error_text_content_column` (PII canary `secret-pii-content-do-not-leak` seeded into the column, asserted absent from response.text) |

## Anti-scope held

`git diff --stat 8e317dc3..HEAD` against the forbidden file list returns ZERO lines changed in any of:

- `src/horus_os/observability/bus.py`
- `src/horus_os/observability/persist.py`
- `src/horus_os/observability/cost.py`
- `src/horus_os/observability/pricing.py`
- `src/horus_os/observability/pricing.json`
- `src/horus_os/agent.py`
- `src/horus_os/tools/loop.py`
- `src/horus_os/storage.py`
- `pyproject.toml`

No new runtime dependencies. No dashboard HTML/JS (Phase 36's job). No CLI surface (Phase 37's job). No opentelemetry references (Phase 38's job).

## Threat register outcomes

- **T-35-01** (Tampering, parse_window window param): **mitigated**. All filters use parameterized `?` placeholders; the window string is never substituted into SQL via string formatting. `ValueError` from `parse_window` converts to `HTTPException(400)` at the route boundary so malformed input never reaches the SQL layer.
- **T-35-02** (Information Disclosure, llm-calls drilldown): **mitigated**. The route's SELECT names columns explicitly and omits the text-content error column. PII canary test (`secret-pii-content-do-not-leak`) seeded into that column never appears in the response body.
- **T-35-03** (Information Disclosure, tool_reliability response): **mitigated**. The query module never references the text-content error column anywhere (file-content grep gate); only `error_type` (exception class name, no user input) surfaces via `last_error_type`.
- **T-35-04** (DoS, llm-calls unbounded scan): **mitigated**. `LIMIT 100` baked into SQL; `?since` filter required; `idx_llm_calls_created_at` index from Phase 32 makes the scan O(log N).
- **T-35-05** (Repudiation, pre-v0.4 cost rendering): **mitigated**. `uncosted_runs` separate counter surfaces NULL-rolled rows so the dashboard cannot silently hide them; pre-v0.4 rows render as `null` plus counter, never as $0 (Pitfall 11).
- **T-35-06** (Information Disclosure, window param probing): **accepted** per register. Low-value side channel; localhost-bound dashboard; no auth surface in v0.4.
- **T-35-07** (Tampering, SQLite injection via tool_name passthrough): **mitigated**. All response fields come from `sqlite3.Row` column access; no user input round-trips back into SQL. Tool/agent names that reach queries.py originate from rows the persister already wrote with parameterized inserts (Phase 32 contract).

## Deviations from plan

None. Plan executed exactly as written through all 7 tasks. One small adjustment surfaced inside Task 6 (and was tracked as part of the Task 6 GREEN commit, not a separate deviation): `agent_totals`'s `total_cost_usd` default changed from `0.0` to `None` when SUM returns NULL (every contributing row's `total_cost_usd IS NULL`). This is the Pitfall 11 honesty contract reaching all the way down to the query primitive: zero is a lie when no cost was ever recorded. The plan's Task 6 acceptance criterion ("pre-v0.4 rows surface as total_cost_usd is None") required this; the simpler alternative of post-processing the route handler would have left the underlying query primitive lying about cost.

No architectural Rule 4 deviations. No new dependencies. No touches to anti-scope files.

## Authentication gates

None encountered. All tests run against in-process fixtures with `TestClient`; no real API calls and no external services.

## Test counts

- Before Phase 35: 520 passed (per Phase 34 SUMMARY).
- After Phase 35: **585 passed, 0 failed, 0 skipped** (65 new tests across 6 new test files; 4 new assertions appended to `tests/test_server_agents.py`).

| New test file | Test count | Covers |
|---------------|-----------|--------|
| tests/observability/test_queries_window.py | 8 | Task 1: parse_window 24h/7d/30d + Nh/Nd + reject malformed/zero/negative + error message anchors input + package re-export |
| tests/observability/test_queries_agent_totals.py | 9 | Task 1: empty DB, run counting, NULL percentiles (Pitfall 10), uncosted_runs (Pitfall 11), NTILE on llm_calls.latency_ms, per-agent grouping, window exclusion, package re-export |
| tests/observability/test_queries_cost_by_agent.py | 9 | Task 2: empty DB, sum excludes NULL + uncosted_runs (Pitfall 11), DESC ordering, window exclusion, cache tokens from llm_calls, tie-breaking by name, zero-runs agents absent, 6dp Python rounding, package re-export |
| tests/observability/test_queries_latency_percentiles.py | 7 | Task 3: empty window NULL contract (Pitfall 10 line 272), n=10 all-at-100ms boundary (Pitfall 10 line 267), n=100 range, n=1 collapse, window exclusion, package re-export, anti-pattern grep gate |
| tests/observability/test_queries_tool_reliability.py | 10 | Task 4: empty DB, retry-aware aggregation, Pitfall 9 regression (retry_then_success NOT error), expected_no_result excluded from denominator, last_error_type/at from MAX(created_at), DESC+name ordering, window exclusion, package re-export, file-content hygiene (Pitfall 7 + Pitfall 9) |
| tests/test_server_observability_routes.py | 19 | Task 5: 4 routes x (empty / valid window / 400 invalid / 503 missing DB) + llm-calls DESC ordering, LIMIT 100, and PII canary absence from JSON body |
| tests/test_server_agents.py (appended) | +4 | Task 6: rollup defaults zero/null when no runs, existing v0.3 keys preserved (backward-compat guard), pre-v0.4 NULL handling (Pitfall 11), mixed v0.3 + v0.4 SUM excludes NULL |

## Out of scope (deliberate)

- **`src/horus_os/observability/bus.py`, `persist.py`, `cost.py`, `pricing.py`, `pricing.json`**: untouched. Phase 33 and 34 own the write path; Phase 35 is read-only.
- **`src/horus_os/agent.py` and `src/horus_os/tools/loop.py`**: untouched. The runner publishes events; Phase 35 only reads what the persister wrote.
- **`src/horus_os/storage.py`**: untouched. Schema v5 from Phase 32 already has every column this plan reads.
- **`pyproject.toml`**: untouched. stdlib only.
- **Phase 36 dashboard tiles**: the queries return the data; the HTML/JS that renders the n>=10 small-sample rule, the staleness banner from Phase 34, the `uncosted_runs` "explained missing dollars" copy, and the drilldown table is Phase 36.
- **Phase 37 CLI `horus-os usage`**: the queries return the same data shapes; the human-readable rendering and column formatting lives in Phase 37.
- **Phase 38 OpenTelemetry adapter**: this plan introduces zero opentelemetry references.
- **Per-window `/api/agents` (`?since=`)**: the existing /api/agents has no window param; the plan hardcoded `7d` for backward compat. If a future need surfaces, that's a Phase 36+ concern.

## Handoff to Phase 36 (dashboard) and Phase 37 (CLI)

Both consumers import from the same module and call the same functions:

```python
from horus_os.observability.queries import (
    parse_window,        # str -> ISO 8601 UTC threshold; ValueError on bad input
    agent_totals,        # (db, window) -> list[dict] per agent
    cost_by_agent,       # (db, window) -> list[dict] per agent, cost-ordered
    latency_p50_p95,     # (db, window) -> dict with p50_ms, p95_ms, sample_count
    tool_reliability,    # (db, window) -> list[dict] per tool, retry-aware
)
```

Function signatures and return shapes are pinned by the tests listed in the Test counts table above. The contracts the consumers can rely on:

- `window` accepts `24h`, `7d`, `30d`, plus any positive integer `Nh` or `Nd`. Anything else raises `ValueError`.
- Percentile fields return Python `None` (JSON null) on empty windows, never 0. `sample_count` is returned alongside so the consumer applies its own n-threshold render rule (the spec says n>=10).
- Cost sums use SQL NULL-skipping; `uncosted_runs` is the separate counter for NULL rows. The consumer renders "$X.XX (Y runs without cost data)" rather than hiding the gap.
- `tool_reliability.success_rate` is None when `success_count + error_count == 0`. The consumer renders an "insufficient data" tile rather than 0% or 100%.
- `tool_reliability.error_count` reflects only `status='error'` rows; `retry_then_success_count` is the separate flakiness signal.

The four HTTP routes return the same data wrapped in JSON envelopes:

| Route | Envelope | Body |
|-------|----------|------|
| `GET /api/observability/cost?since=7d` | `{"agents": [...]}` | list of `cost_by_agent` rows |
| `GET /api/observability/latency?since=7d` | `{"p50_ms", "p95_ms", "sample_count"}` | dict from `latency_p50_p95` |
| `GET /api/observability/tools?since=7d` | `{"tools": [...]}` | list of `tool_reliability` rows |
| `GET /api/observability/llm-calls?since=7d` | `{"calls": [...]}` | up to 100 newest llm_calls rows, DESC by created_at; explicit column list omits the text-content error column |

All four return 400 on invalid window with `invalid window:` in the detail, and 503 when the database file does not exist (matches the existing `/api/traces` and `/api/agents` contract).

The `/api/agents` route now returns per-agent rollup fields merged into each row alongside the existing v0.3 keys:

```json
{
  "name": "default",
  "system_prompt": "...",
  "default_model": null,
  "allowed_tools": null,
  "memory_scope": null,
  "created_at": "...",
  "updated_at": "...",
  "last_activity_at": "...",
  "total_runs": 0,
  "total_cost_usd": null,
  "latency_p50_ms": null,
  "latency_p95_ms": null,
  "uncosted_runs": 0
}
```

DASH-4-04 backend is done. Phase 36 reads these fields and ships the dashboard render.

## Self-Check

Verified after writing this SUMMARY:

- All 12 plan commits (plus the Task 7 style commit and this docs commit) exist with the required `test(35-01)` / `feat(35-01)` / `style(35-01)` / `docs(35-01)` prefixes.
- All files in `key-files.created` exist under the repo root.
- All files in `key-files.modified` exist under the repo root.
- `.venv/bin/python -m pytest tests/ -q` exits 0 with 585 passed.
- `.venv/bin/ruff check src/ tests/` exits 0.
- `.venv/bin/ruff format --check src/ tests/` exits 0 (all 112 files formatted).
- `.venv/bin/python scripts/lint_no_wallclock.py` exits 0.
- `grep -c "NTILE(100)" src/horus_os/observability/queries.py` returns 4 (>= 2 required).
- `grep -Ec "statistics\.(quantiles|median|mean)" src/horus_os/observability/queries.py` returns 0.
- `grep -c "error_message" src/horus_os/observability/queries.py` returns 0.
- `grep -c "/api/observability/" src/horus_os/server/api.py` returns 4.
- Anti-scope diff against `bus.py`, `persist.py`, `cost.py`, `pricing.py`, `pricing.json`, `agent.py`, `tools/loop.py`, `storage.py`, `pyproject.toml` is empty.
- No modifications to `.planning/STATE.md` or `.planning/ROADMAP.md` (worktree mode; orchestrator owns those writes after merge-back).

## Self-Check: PASSED
