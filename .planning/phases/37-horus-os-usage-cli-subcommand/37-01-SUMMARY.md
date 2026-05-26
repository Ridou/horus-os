---
phase: 37-horus-os-usage-cli-subcommand
plan: "01"
subsystem: cli
tags: [cli, usage, observability, v0.4, usage-01, usage-02, usage-03, usage-04, stdlib-only, pitfall-float-precision]

# Dependency graph
requires:
  - phase: "35-01"  # observability/queries.py (cost_by_agent, tool_reliability, parse_window) + /api/observability/* routes
  - phase: "36-01"  # parallel sibling; both consume the Phase 35 substrate. Phase 37 does not depend on dashboard code but ships AFTER 36 in the ROADMAP execution order
provides:
  - "src/horus_os/cli/usage_cmd.py: run_usage(args, *, stdout, stderr) -> int handler mirroring traces_cmd.run_traces shape; three formatters (_format_json / _format_csv / _format_table) sharing a _round_row helper for USAGE-04 cross-format precision parity"
  - "src/horus_os/__main__.py: `usage` subparser registered with --data-dir / --since / --format / --by flags"
  - "src/horus_os/cli/__init__.py: run_usage re-exported alphabetically in package __all__"
  - "src/horus_os/observability/queries.py: ADDITIVE new public function cost_by_model(db, window) -> list[dict]; existing 5 functions UNMODIFIED (diff against parse_window, agent_totals, cost_by_agent, latency_p50_p95, tool_reliability is zero lines)"
  - "src/horus_os/observability/__init__.py: cost_by_model added to import block and __all__ alphabetically"
  - "src/horus_os/server/api.py: ADDITIVE new GET /api/observability/cost-by-model route returning {\"models\": [...]} with the SAME row shape cost_by_model returns; existing 5 observability routes UNMODIFIED"
  - "docs/CLI.md: new CLI reference doc with horus-os usage subcommand reference plus JSON output schema (one per-row table per --by slice) plus precision contract plus worked example"
  - "tests/fixtures/usage_output_schema.json: pinned JSON output fixture; schema drift fails tests/test_cli_usage.py::test_json_format_matches_pinned_fixture_schema"

requirements-completed:
  - USAGE-01  # `horus-os usage --since 7d` returns a usage report; --since accepts 24h, 7d, 30d, Nh, Nd
  - USAGE-02  # --format json|csv|table; JSON schema documented in docs/CLI.md and pinned by fixture
  - USAGE-03  # --by model|tool|agent slices; CLI --by model --format json output equals /api/observability/cost-by-model route body byte-for-byte over the same window
  - USAGE-04  # costs render rounded to 6 decimals via Python round(value, 6); durations as int ms; canonical 0.006150 renders exactly 0.00615, NEVER 0.006149999999 across all three formats

# Tech stack
tech-stack:
  added: []
  patterns:
    - "stdlib only: argparse, csv, io, json, typing. Zero new pyproject.toml dependencies (git diff pyproject.toml is empty)"
    - "USAGE-04 float-precision contract: Python round(value, 6) BEFORE serialization via a shared _round_row helper; NOT format strings, NOT json.dumps default behavior, NOT SQLite ROUND (which is platform-variable across the 3-OS CI matrix)"
    - "USAGE-04 cross-format parity: same _round_row helper drives JSON, CSV, AND table; the canonical 0.006150 seed renders identically in all three formats and the anti-canary substring 0.006149 is ABSENT from every output (pinned by test_all_three_formats_emit_same_numeric_cost_for_canonical_row)"
    - "USAGE-03 byte-for-byte route parity: CLI --by model --format json rows equal /api/observability/cost-by-model models element-by-element because both call the same cost_by_model(db, window) function (pinned by test_usage_by_model_byte_for_byte_parity_with_route)"
    - "USAGE-02 schema pin via tests/fixtures/usage_output_schema.json: any change to keys, ordering, precision, or envelope fails test_json_format_matches_pinned_fixture_schema loudly so schema drift cannot ship silently"
    - "JSON envelope shape {by, since, rows} with sort_keys=True for diff-stable output across runs; rows is an empty list (not absent) on empty windows"
    - "CSV envelope: csv.DictWriter with alphabetical fieldnames matching JSON sort_keys ordering; empty rows return empty string so wc -l returns 0; None renders as empty cell (csv default), distinguishable from `0` so Pitfall 11 honesty contract survives in CSV"
    - "Table envelope: column-aligned printer mirroring traces_cmd._format_table with 30-char column cap and ellipsis truncate per PITFALLS.md table-truncate row; None renders as `-` (single hyphen) so the NULL contract has a visual analog that never reads as 0; empty windows render `(no usage data in window)` so operators distinguish empty from broken"
    - "Pitfall 11 honesty survives across all three formats: cost_by_agent's existing contract (None converted to 0.0 inside the function family for backward compatibility) is preserved; the uncosted_runs / uncosted_calls counter is the visible NULL signal; CSV writes empty cells for genuine None (success_rate on zero-denominator tool rows); table writes `-` for genuine None"
    - "cost_by_model is purely additive: existing 5 query functions UNMODIFIED. The diff for parse_window, agent_totals, cost_by_agent, latency_p50_p95, tool_reliability is zero lines. Mirror of cost_by_agent's structure: one CTE filtering by created_at >= ?, GROUP BY model + provider, Python round(value, 6) at the boundary, ORDER BY COALESCE(SUM(cost_usd), 0) DESC then model ASC"
    - "/api/observability/cost-by-model route envelope key is `models` matching the noun convention used by the existing 5 observability routes (cost -> agents, tools -> tools, latency -> {p50, p95, sample_count}, llm-calls -> calls, cost-by-model -> models)"
    - "--since validation happens at the CLI boundary before the DB hit: parse_window(args.since) raises ValueError which run_usage converts to `invalid window:` on stderr plus return 1, mirroring the route's ValueError -> HTTPException(400) hop"
    - "Auth gate posture inherited from Phase 35: no auth surface in v0.4 (localhost-bound for the route, user-shell-bound for the CLI); same as the other 5 observability routes"

# Key files
key-files:
  created:
    - src/horus_os/cli/usage_cmd.py
    - docs/CLI.md
    - tests/fixtures/usage_output_schema.json
    - tests/test_cli_usage.py
    - tests/observability/test_queries_cost_by_model.py
    - .planning/phases/37-horus-os-usage-cli-subcommand/37-01-SUMMARY.md
  modified:
    - src/horus_os/__main__.py
    - src/horus_os/cli/__init__.py
    - src/horus_os/observability/queries.py
    - src/horus_os/observability/__init__.py
    - src/horus_os/server/api.py
    - tests/test_server_observability_routes.py

# Metrics
duration: 35m
completed: 2026-05-26
total-tests: 644 passed
commits: 4
---

# Phase 37 Plan 01 Summary: horus-os usage CLI subcommand

## What shipped

Four atomic commits deliver the `horus-os usage --since 7d --format json|csv|table --by model|tool|agent` subcommand. The CLI consumes the Phase 35 `observability/queries.py` substrate (`cost_by_agent`, `tool_reliability`) plus ONE purely additive new query (`cost_by_model`) and ONE purely additive route (`/api/observability/cost-by-model`). USAGE-03 byte-for-byte parity holds because CLI `--by model --format json` rows are the same Python list of dicts the route serializes under a different envelope key. USAGE-04 float-precision contract holds because the shared `_round_row` helper applies `round(value, 6)` BEFORE serialization in all three formatters; the canonical PRICE-02 cost `0.006150` renders exactly across JSON, CSV, AND table mode and the anti-canary substring `0.006149` is absent from every output.

Zero new dependencies (`git diff pyproject.toml` empty). Anti-scope held: zero touches to `bus.py`, `persist.py`, `cost.py`, `pricing.py`, `pricing.json`, `agent.py`, `tools/loop.py`, `storage.py`, or any pre-existing query function in `queries.py`. End-to-end smoke test passing: `horus-os init` then `horus-os usage --since 7d` returns rc=0 with `(no usage data in window)` on stdout; `horus-os usage --since garbage` returns rc=1 with `invalid window: 'garbage'; expected forms like '24h', '7d', '30d'` on stderr.

| Commit  | Type     | Title                                                                                              |
| ------- | -------- | -------------------------------------------------------------------------------------------------- |
| a00b9cc | feat(37) | horus-os usage subcommand skeleton plus argparse wiring                                            |
| c37d50a | feat(37) | JSON formatter for usage report plus precision contract plus pinned fixture                        |
| dfbe5da | feat(37) | CSV and table formatters with USAGE-04 precision parity across formats                             |
| 3744dd3 | feat(37) | --by model slice plus additive cost_by_model query plus byte-for-byte route parity                 |

## Requirements satisfied

- **USAGE-01** (`horus-os usage --since 7d` returns a usage report; `--since` accepts `24h`, `7d`, `30d`, and any `Nh`/`Nd` form; invalid input exits non-zero with `invalid window:` on stderr): Task 1. `run_usage` calls `parse_window(args.since)` at the CLI boundary BEFORE any DB hit so a bogus arg fails fast. The ValueError message from `parse_window` starts with `invalid window:` and includes the rejected input. Pinned by `tests/test_cli_usage.py::test_usage_invalid_since_writes_invalid_window_to_stderr` and `::test_usage_missing_db_writes_to_stderr_and_returns_1`.
- **USAGE-02** (`--format json|csv|table` controls output shape; JSON schema documented in `docs/CLI.md` and pinned by test against fixture): Tasks 2-3. JSON envelope `{by, since, rows}` with `sort_keys=True`; per-row shape documented in `docs/CLI.md` under `## horus-os usage > ### JSON output schema` (one table per `--by` slice). Fixture pin at `tests/fixtures/usage_output_schema.json` contains the canonical PRICE-02 row including the literal `0.006150` substring. Pinned by `tests/test_cli_usage.py::test_json_format_matches_pinned_fixture_schema` and `::test_docs_cli_md_documents_horus_os_usage_subcommand`.
- **USAGE-03** (`--by model|tool|agent` slices the report; CLI `--by model --format json` output equals `/api/observability/cost-by-model` route body byte-for-byte over the same window where data overlaps): Task 4. `--by agent` calls `cost_by_agent`; `--by tool` calls `tool_reliability`; `--by model` calls the new additive `cost_by_model` which also backs the new route. Envelope keys differ by design (CLI `rows`, route `models`) but the inner row list is the same Python `list[dict]` object reference modulo serialization. Pinned by `tests/test_cli_usage.py::test_usage_by_model_byte_for_byte_parity_with_route` which seeds a 2-model DB, calls both surfaces, and asserts `cli_payload["rows"] == route_payload["models"]` element-by-element.
- **USAGE-04** (costs render rounded to 6 decimals via `round(value, 6)`; durations as integer ms; same numeric values across all three formats; canonical 0.006150 renders exactly, NEVER 0.006149999999): Tasks 2-3. Shared `_round_row` helper applies `round(value, 6)` BEFORE serialization for keys in `{total_cost_usd, cost_usd, success_rate}`, casts integers for `_ms`/`_tokens`/`_count`/`_runs`/`_calls` suffix fields, and passes None through unchanged. Pinned by `tests/test_cli_usage.py::test_all_three_formats_emit_same_numeric_cost_for_canonical_row` (cross-format parity), `::test_json_format_canonical_cost_renders_exactly_six_decimals` (anti-canary substring 0.006149 ABSENT in JSON), `::test_csv_format_canonical_cost_no_float_precision_noise` (anti-canary in CSV), `::test_table_format_canonical_renders_six_decimal_cost` (canonical cost present, anti-canary absent in table).

## ROADMAP Success Criteria

- [x] **SC1 (USAGE-01):** `horus-os usage --since 7d` returns a usage report over a configurable window; `--since` accepts `24h`, `7d`, `30d`, or any `Nh`/`Nd` form. Pinned by `tests/test_cli_usage.py::test_usage_subparser_registered_with_choices` + `::test_usage_invalid_since_writes_invalid_window_to_stderr`. End-to-end smoke: `horus-os usage --since 7d` against a real DB returns rc=0; `--since garbage` returns rc=1 with `invalid window:` on stderr. [Task 1]
- [x] **SC2 (USAGE-02):** `--format json|csv|table` controls output shape; the JSON output schema is documented in `docs/CLI.md` and pinned by a test that diffs the output against `tests/fixtures/usage_output_schema.json`. Pinned by `::test_json_format_matches_pinned_fixture_schema` (schema drift fails this test loudly) + `::test_docs_cli_md_documents_horus_os_usage_subcommand` (doc presence guard). [Tasks 2-3]
- [x] **SC3 (USAGE-03):** `--by model|tool|agent` slices the report into per-model, per-tool, or per-agent views; output for each shape matches the corresponding `/api/observability/*` route byte-for-byte where the data overlaps. Pinned by `::test_usage_by_model_byte_for_byte_parity_with_route` (the load-bearing assertion: CLI rows equal route models element-by-element over a multi-row seeded DB) + `::test_usage_by_model_json_canonical_renders_six_decimals` + `::test_usage_by_model_csv_matches_json_costs`. [Task 4]
- [x] **SC4 (USAGE-04, Pitfall float-precision UX trap):** Costs render rounded to 6 decimal places, durations to integer ms, consistent units across all three formats; a `jq` pipe on the JSON output never trips on float-precision noise like `0.04200000000000001`. Pinned by `::test_all_three_formats_emit_same_numeric_cost_for_canonical_row` (cross-format parity), `::test_json_format_canonical_cost_renders_exactly_six_decimals`, `::test_csv_format_canonical_cost_no_float_precision_noise`, `::test_table_format_canonical_renders_six_decimal_cost`. [Tasks 2-3]

## Pitfalls guarded

| Pitfall | Owner Task | Pin Test |
|---------|-----------|----------|
| Float-precision UX trap (PITFALLS.md line 403: `0.04200000000000001` breaking `jq` and `column` pipes) | Tasks 2-3 | `tests/test_cli_usage.py::test_json_format_canonical_cost_renders_exactly_six_decimals` (anti-canary substring `0.006149` ABSENT from JSON, `0.006150000000` ABSENT); `::test_csv_format_canonical_cost_no_float_precision_noise` (same anti-canary in CSV); `::test_table_format_canonical_renders_six_decimal_cost` (canonical present, anti-canary absent in table); `::test_all_three_formats_emit_same_numeric_cost_for_canonical_row` (cross-format parity assertion via pytest.approx with abs=1e-9) |
| Table-truncate (PITFALLS.md line 400: long agent names stretch the row off-screen) | Task 3 | `tests/test_cli_usage.py::test_table_format_long_agent_name_truncates_with_ellipsis` (40-char agent name seeded; ellipsis present in output; full 40-char name absent) |
| Pitfall 11 (NULL cost surfaces honestly, never as `0`) | Tasks 2-3 | `tests/test_cli_usage.py::test_json_format_preserves_none_for_uncosted_run` (JSON keeps `uncosted_runs` counter as the visible NULL signal); `::test_csv_format_uncosted_run_writes_empty_cell_not_zero` (CSV counter surfaces); `::test_table_format_uncosted_run_renders_hyphen_not_zero` (table renders `-`, never `0`); inherited cost_by_agent contract from Phase 35 unchanged |

## Anti-scope held

`git diff --stat $(git merge-base main HEAD)..HEAD` against the forbidden file list returns ZERO lines changed in any of:

- `src/horus_os/observability/bus.py`
- `src/horus_os/observability/persist.py`
- `src/horus_os/observability/cost.py`
- `src/horus_os/observability/pricing.py`
- `src/horus_os/observability/pricing.json`
- `src/horus_os/agent.py`
- `src/horus_os/tools/loop.py`
- `src/horus_os/storage.py`
- `pyproject.toml`

Existing query functions in `observability/queries.py` are also UNMODIFIED. The diff against `parse_window`, `agent_totals`, `cost_by_agent`, `latency_p50_p95`, `tool_reliability` is zero behavioral lines (only the `__all__` list grew by one entry and the new `cost_by_model` function was inserted between `cost_by_agent` and `latency_p50_p95`). No dashboard changes (Phase 36 done; index.html untouched). No opentelemetry references (Phase 38). No new pricing entries (Phase 34 owns pricing.json).

## Threat register outcomes

| Threat ID | Disposition | Outcome |
|-----------|-------------|---------|
| T-37-01 (Tampering, `--since` CLI arg) | mitigate | `parse_window(args.since)` raises `ValueError` on malformed input; `run_usage` converts to `stderr.write(f"{exc}\n")` plus `return 1` BEFORE any SQL runs. Mirrors the route boundary at server/api.py:334-335. Same `parse_window` substrate pinned by `tests/observability/test_queries_window.py` (8 tests, Phase 35) plus `test_usage_invalid_since_writes_invalid_window_to_stderr`. |
| T-37-02 (Tampering, `--data-dir` to filesystem) | mitigate | `Config.load(Path(args.data_dir).expanduser())` follows traces_cmd.run_traces pattern. No new file writes (read-only subcommand); `db_path.exists()` guard returns rc=1 BEFORE any DB open if the path is bogus. Pinned by `test_usage_missing_db_writes_to_stderr_and_returns_1`. |
| T-37-03 (Info Disclosure, CLI cost output) | accept | Costs and token counts are user's own data; CLI runs in user's own shell; no PII in cost rollups. cost_by_model never touches `tool_invocations` so no text-content error column is referenced anywhere in the new code path. |
| T-37-04 (Info Disclosure, new /cost-by-model route) | accept | Per Phase 36 T-36-02 register entry: localhost-bound, non-PII metadata, no auth surface in v0.4. Same posture as the other 5 observability routes. |
| T-37-05 (Tampering / SQL injection, `?since=` route + cost_by_model SQL) | mitigate | All filters use parameterized `?` placeholders; `since` converted to ISO threshold via `parse_window` before reaching SQL; cost_by_model's CTE never substitutes user input via Python string formatting. Mirrors Phase 35 T-35-01 contract verbatim. |
| T-37-06 (Repudiation, CLI/route disagreement) | mitigate | USAGE-03 byte-for-byte parity test (`test_usage_by_model_byte_for_byte_parity_with_route`) compares CLI rows element-by-element against route models. Both call the same `cost_by_model(db, window)` so they cannot drift. Schema drift is caught by `test_json_format_matches_pinned_fixture_schema` against the pinned fixture. |
| T-37-07 (DoS, cost_by_model unbounded scan) | mitigate | `idx_llm_calls_created_at` index from Phase 32 makes the WHERE created_at >= ? scan O(log N). The `?since=` filter is required (default `7d`). GROUP BY model + provider naturally caps rows at the model-count (typically 5-10 models per user). |
| T-37-08 (Info Disclosure, float-precision noise to jq consumers) | mitigate | USAGE-04 contract: Python `round(value, 6)` BEFORE `json.dumps` (NOT after, NOT via format string, NOT via SQLite ROUND). Canonical fixture pins `0.006150`; anti-canary tests assert `0.006149` substring absent from JSON, CSV, AND table output. Cross-format parity in `test_all_three_formats_emit_same_numeric_cost_for_canonical_row`. |

## Deviations from plan

None. The 5 tasks executed exactly as planned. The only intra-task adjustments were:

1. **Task 1 / Task 2 / Task 3 / Task 4 NotImplementedError test churn**: each task progressively replaces a placeholder with a live implementation, which means the prior task's "stub assertion" test needs to retarget. Plan text already anticipated this ("Re-run the existing Task 1 tests; they should still pass since dispatch behavior unchanged for csv/table/model"). Specifically: Task 2 retargeted the agent+json stub test to agent+csv (still NotImplementedError); Task 3 retargeted both stub tests to assert live success since CSV and table now work; Task 4 retargeted the model+table stub test to assert live success. Each retarget preserves the original test's intent (dispatch hits the right code path) while reflecting the now-live behavior.

2. **Task 2 _format_json signature**: the plan instructed `_format_json(rows, by=args.by, since=args.since)` with the envelope keys passed in. Implemented as written. No behavioral deviation.

3. **Task 4 ruff format pass on queries.py**: the inserted `cost_by_model` function had one line slightly over the project's 100-char limit; `ruff format` collapsed it. Logical content unchanged; existing functions in queries.py untouched.

## Authentication gates

None. The usage subcommand is read-only and runs in the user's own shell. The new route inherits the localhost-bound posture of the existing 5 observability routes (no auth surface in v0.4).

## Test counts

- **Before this plan**: 607 passed (Phase 36 baseline)
- **After this plan**: 644 passed (+37 new)
- **Breakdown by file**:
  - `tests/test_cli_usage.py`: 26 tests (NEW file)
  - `tests/observability/test_queries_cost_by_model.py`: 7 tests (NEW file)
  - `tests/test_server_observability_routes.py`: 4 NEW tests for /api/observability/cost-by-model route (19 -> 23 total in file)
- **All gates green**: `ruff check src/ tests/` clean; `ruff format --check src/ tests/` clean; `python scripts/lint_no_wallclock.py` clean.

## Out of scope (deliberate)

- **Phase 38 OpenTelemetry adapter**: opt-in OTLP exporter is the next phase. The CLI does not depend on OTel and OTel does not depend on the CLI.
- **Phase 39 release gate / migration**: v3->v4 schema migration is additive and was landed in Phase 32; the v0.4 -> v0.4.x release cut is Phase 39's job.
- **`--by latency` slice**: USAGE-03 only specifies `agent|tool|model`; `latency_p50_p95` is a separate global aggregate that does not group naturally. If a future operator wants per-agent latency tables, agent_totals already carries `latency_p50_ms` / `latency_p95_ms` per agent; a future Phase can add `--by agent-latency` if the use case emerges.
- **CLI cost / latency drilldown subcommands**: this phase ships ONE subcommand (`usage`) with the three documented slices. A future Phase can add `horus-os llm-calls` if direct row-level drilldown becomes a CLI use case (the route already exists at `/api/observability/llm-calls` from Phase 35).
- **Pagination on `--by` outputs**: GROUP BY caps row counts naturally (5-10 models, 1-N agents, 1-N tools). If a user runs hundreds of agents, `wc -l` on CSV output is the user-side filter; native CLI pagination is a v0.5 ergonomic concern.

## Forward dependencies for Phase 38

Phase 38 ships the opt-in OpenTelemetry adapter as a v0.3-style adapter. It does NOT depend on the Phase 37 CLI. The CLI is stable substrate: future Phases can add new `--by` slices or new subcommands additively without breaking the `--by agent|tool|model --format json|csv|table` contracts pinned here.

The new `cost_by_model` query function is a natural span attribute source if Phase 38 wants per-model rollups in OTLP exports, but Phase 38's design (opt-in extra, lifecycle hooks) means it builds on the persister event stream rather than the query module.

## Known Stubs

None. All three formatters are live. `--by model` is live. The route is live. No placeholder code remains in the shipped surface.

## Self-Check

- [x] `tests/test_cli_usage.py` exists with 26 tests
- [x] `tests/observability/test_queries_cost_by_model.py` exists with 7 tests
- [x] `tests/test_server_observability_routes.py` extended with 4 new route tests (23 total, was 19)
- [x] `src/horus_os/cli/usage_cmd.py` exists with `run_usage` plus `_format_json` / `_format_csv` / `_format_table` plus shared `_round_row` helper
- [x] `src/horus_os/__main__.py` has `usage_p = sub.add_parser("usage", ...)` plus four flags plus `set_defaults(func=run_usage)`
- [x] `src/horus_os/cli/__init__.py` re-exports `run_usage` in `__all__`
- [x] `src/horus_os/observability/queries.py` has `def cost_by_model` (NEW); existing 5 functions untouched
- [x] `src/horus_os/observability/__init__.py` re-exports `cost_by_model` in `__all__`
- [x] `src/horus_os/server/api.py` has `@app.get("/api/observability/cost-by-model")` route
- [x] `docs/CLI.md` exists with `## horus-os usage`, `### JSON output schema`, `### Precision contract`, `0.006150` literal, all four flag references
- [x] `tests/fixtures/usage_output_schema.json` exists, parses as valid JSON, contains the literal substring `0.006150`, does NOT contain `0.00614`
- [x] `pytest tests/` returns 644 passed (607 baseline + 37 new)
- [x] `ruff check src/ tests/` exits 0
- [x] `ruff format --check src/ tests/` exits 0
- [x] `python scripts/lint_no_wallclock.py` exits 0
- [x] `grep -c 'NTILE' src/horus_os/observability/queries.py` returns 5 (preserved from Phase 35)
- [x] `grep -c 'error_message' src/horus_os/observability/queries.py` returns 0 (Pitfalls 7+9 hygiene maintained)
- [x] `git diff --stat $(git merge-base main HEAD)..HEAD -- <anti-scope file list>` returns zero lines changed
- [x] `python -m horus_os init` then `python -m horus_os usage --since 7d` runs end-to-end (rc=0, `(no usage data in window)` on stdout)
- [x] `python -m horus_os usage --since garbage` runs end-to-end (rc=1, `invalid window: 'garbage'; expected forms like '24h', '7d', '30d'` on stderr)
- [x] Four atomic commits with conventional-commit `feat(37):` prefix (a00b9cc, c37d50a, dfbe5da, 3744dd3)
