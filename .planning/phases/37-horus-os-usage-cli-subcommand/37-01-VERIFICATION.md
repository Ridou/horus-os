---
phase: 37-horus-os-usage-cli-subcommand
verified: 2026-05-26T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Phase 37 Plan 01 Verification Report: horus-os usage CLI subcommand

**Phase Goal:** Ship `horus-os usage --since 7d --format json|csv|table --by model|tool|agent` reusing Phase 35 queries.py. Stdlib only.
**Verified:** 2026-05-26
**Status:** passed
**Re-verification:** No, initial verification.

## Goal Achievement

### Observable Truths (USAGE-01..04)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | USAGE-01: `horus-os usage --since 7d` runs end-to-end; --since validates Nh/Nd and exits non-zero with `invalid window:` on bad input | VERIFIED | Live run with `--since 7d` against fresh init'd DB returned rc=0 and `(no usage data in window)` to stdout. Live `--since garbage` returned rc=1 with stderr `invalid window: 'garbage'; expected forms like '24h', '7d', '30d'`. |
| 2 | USAGE-02: `--format json\|csv\|table` controls output; JSON schema pinned by fixture | VERIFIED | `tests/fixtures/usage_output_schema.json` exists with canonical row containing literal `0.006150`; `docs/CLI.md` contains `## horus-os usage`, `### JSON output schema`, `### Precision contract` (3/3 sections). `test_json_format_matches_pinned_fixture_schema` passes. |
| 3 | USAGE-03: `--by model\|tool\|agent` slices; CLI `--by model --format json` matches `/api/observability/cost-by-model` byte-for-byte | VERIFIED | `test_usage_by_model_byte_for_byte_parity_with_route` passes; route at `src/horus_os/server/api.py:339`; `cost_by_model` re-exported in `observability/__init__.py` lines 29 + 76. |
| 4 | USAGE-04: costs round to 6 decimals via Python `round(value, 6)`; canonical 0.006150 renders exactly, 0.006149 absent across JSON/CSV/table | VERIFIED | `test_json_format_canonical_cost_renders_exactly_six_decimals`, `test_all_three_formats_emit_same_numeric_cost_for_canonical_row`, `test_csv_format_canonical_cost_no_float_precision_noise`, `test_table_format_canonical_renders_six_decimal_cost` all pass. Fixture grep: `0.006150` present, `0.006149` absent. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/horus_os/cli/usage_cmd.py` | run_usage handler + 3 formatters + dispatch by --by | VERIFIED | 204 lines (>= 80 min); `def run_usage` present at line 43; `_format_json` / `_format_csv` / `_format_table` + shared `_round_row` helper present; imports `cost_by_agent, cost_by_model, parse_window, tool_reliability` from queries.py |
| `src/horus_os/cli/__init__.py` | run_usage exported in __all__ | VERIFIED | `from horus_os.cli.usage_cmd import run_usage` at line 17; `run_usage` in `__all__` (line 19) |
| `src/horus_os/__main__.py` | usage subparser with --since/--format/--by/--data-dir | VERIFIED | `usage_p = sub.add_parser("usage", ...)` at line 209; --data-dir, --since (default 7d), --format (choices json/csv/table, default table), --by (choices agent/tool/model, default agent), `set_defaults(func=run_usage)` |
| `src/horus_os/observability/queries.py` | ADDITIVE cost_by_model; existing 5 functions UNMODIFIED | VERIFIED | `grep -c "def cost_by_model"` returns 1; `git diff 8a2f137..HEAD` shows zero `^-.*def (parse_window\|agent_totals\|cost_by_agent\|latency_p50_p95\|tool_reliability)` matches; cost_by_model placed at line 298 between cost_by_agent (197) and latency_p50_p95 (377) alphabetically |
| `src/horus_os/observability/__init__.py` | cost_by_model added to imports + __all__ | VERIFIED | `cost_by_model,` at line 29 (imports) and line 76 (__all__) |
| `src/horus_os/server/api.py` | ADDITIVE /api/observability/cost-by-model route returning {"models": [...]} | VERIFIED | `@app.get("/api/observability/cost-by-model")` at line 339; route returns `{"models": rows}` |
| `docs/CLI.md` | usage subcommand reference + JSON schema + precision contract | VERIFIED | 134 lines; contains all 3 required H2/H3 sections; canonical `0.006150` literal present in example |
| `tests/fixtures/usage_output_schema.json` | Pinned JSON fixture for schema drift | VERIFIED | Valid JSON; contains `0.006150` literal; does NOT contain `0.006149` (anti-canary clean) |
| `tests/test_cli_usage.py` | 26 e2e tests covering all USAGE-01..04 contracts | VERIFIED | 505 lines (>= 120 min); 26 tests; all pass |
| `tests/observability/test_queries_cost_by_model.py` | Unit tests for cost_by_model | VERIFIED | 173 lines (>= 60 min) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `cli/usage_cmd.py` | `observability/queries.py` | import + call cost_by_agent / cost_by_model / tool_reliability | WIRED | Lines 23-28 import all four functions; dispatch in run_usage lines 62-67 calls each |
| `cli/usage_cmd.py` | `storage.py` | Config.load + Database(cfg.db_path) + db.exists guard | WIRED | Line 45 Config.load, line 46-48 db_path.exists guard returning rc=1 to stderr, line 60 Database construction |
| `__main__.py` | `cli/usage_cmd.py` | import run_usage + sub.add_parser('usage') + set_defaults(func=run_usage) | WIRED | Line 11 import, line 209 subparser, line 233 set_defaults |
| `test_cli_usage.py` | `server/api.py` | TestClient.get('/api/observability/cost-by-model') byte-for-byte vs run_usage(--by model --format json) | WIRED | `test_usage_by_model_byte_for_byte_parity_with_route` passes |

### Behavioral Spot-Checks (Live)

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `horus-os usage --since 7d` end-to-end | `python -m horus_os usage --data-dir /tmp/phase37_test_dir --since 7d` | rc=0, stdout: `(no usage data in window)` | PASS |
| Invalid window fails fast | `python -m horus_os usage --data-dir /tmp/phase37_test_dir --since garbage` | rc=1, stderr: `invalid window: 'garbage'; expected forms like '24h', '7d', '30d'` | PASS |
| JSON format with envelope | `python -m horus_os usage ... --since 24h --format json --by agent` | rc=0, valid JSON `{"by": "agent", "rows": [], "since": "24h"}` | PASS |
| Full pytest suite | `python -m pytest tests/ -q` | 644 passed in 18.52s | PASS |
| usage CLI tests | `python -m pytest tests/test_cli_usage.py -q` | 26 passed in 0.53s | PASS |
| USAGE-03 byte-for-byte parity test | `python -m pytest tests/test_cli_usage.py::test_usage_by_model_byte_for_byte_parity_with_route -v` | PASSED | PASS |
| USAGE-04 cross-format precision parity test | `python -m pytest tests/test_cli_usage.py::test_all_three_formats_emit_same_numeric_cost_for_canonical_row -v` | PASSED | PASS |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| USAGE-01 | `horus-os usage --since 7d` returns a usage report over a configurable window | SATISFIED | Live e2e + `test_usage_subparser_registered_with_choices` + `test_usage_invalid_since_writes_invalid_window_to_stderr` |
| USAGE-02 | --format json\|csv\|table controls output shape; JSON schema documented in docs/CLI.md and pinned by a test | SATISFIED | `test_json_format_matches_pinned_fixture_schema` + `test_docs_cli_md_documents_horus_os_usage_subcommand` |
| USAGE-03 | --by model\|tool\|agent slices into per-model/tool/agent views | SATISFIED | `test_usage_by_model_byte_for_byte_parity_with_route` element-by-element match |
| USAGE-04 | Costs rounded to 6 decimals, durations to integer ms, consistent across formats | SATISFIED | `test_all_three_formats_emit_same_numeric_cost_for_canonical_row` + anti-canary substring tests across JSON/CSV/table |

### Anti-Scope Hold

`git diff 8a2f137..HEAD --name-only | grep -E "(bus|persist|cost|pricing|agent|tools/loop|storage)\.py|pyproject"` returns ZERO matches. No touches to:
- `src/horus_os/observability/bus.py`
- `src/horus_os/observability/persist.py`
- `src/horus_os/observability/cost.py`
- `src/horus_os/observability/pricing.py`
- `src/horus_os/agent.py`
- `src/horus_os/tools/loop.py`
- `src/horus_os/storage.py`
- `pyproject.toml`

Existing queries.py functions (parse_window, agent_totals, cost_by_agent, latency_p50_p95, tool_reliability) UNMODIFIED — diff for `^-.*def (...)` returns zero matches.

### Anti-Patterns Found

None. No TBD/FIXME/XXX markers introduced. No stubs remaining. All formatters live, --by model live, route live.

### Test Counts

- Full suite: **644 passed** in 18.52s (matches SUMMARY claim)
- `tests/test_cli_usage.py`: 26 tests, all pass
- Phase 36 baseline 607 + 37 new = 644

### Gaps Summary

No gaps. All 4 USAGE requirements satisfied, all 4 ROADMAP success criteria pinned by tests, anti-scope hold confirmed, full pytest green, live CLI smoke tests pass, anti-canary float-precision substring absent from fixture.

---

_Verified: 2026-05-26_
_Verifier: Claude (gsd-verifier)_
