---
phase: 36-observability-dashboard-tab
plan: "01"
subsystem: dashboard
tags: [dashboard, observability, frontend, vanilla-js, pitfall-5, pitfall-10, pitfall-11, v0.4, dash-4]

# Dependency graph
requires:
  - phase: "34-01"  # PricingTable.is_stale + updated_at_age_days (banner substrate)
  - phase: "35-01"  # /api/observability/{cost,latency,tools,llm-calls} + /api/agents rollup fields
provides:
  - "src/horus_os/server/static/index.html: 6th tab (Observability) with cost-by-agent CSS bar chart + latency p50/p95 table + tool reliability table + window selector (24h/7d/30d) + 5s polling cleared on tab switch"
  - "src/horus_os/server/static/index.html: Pitfall 10 small-sample render (sample_count < 10 -> em-dash with hover 'need at least 10 runs for percentile')"
  - "src/horus_os/server/static/index.html: Pitfall 11 NULL render on /agents tab (total_cost_usd === null -> em-dash with hover 'no cost data captured before v0.4') + uncosted-runs explanatory tile aggregating across rows"
  - "src/horus_os/server/static/index.html: Pitfall 5 pricing-staleness banner (yellow at 30 days, red at 90+; copy includes HORUS_OS_PRICING_PATH verbatim)"
  - "src/horus_os/server/static/index.html: /agents tab extended with cost / p50 ms / p95 ms / uncosted columns sourced from Phase 35 backend extension"
  - "src/horus_os/server/api.py: GET /api/observability/pricing-status returning {updated_at, updated_at_age_days, is_stale}"
  - "src/horus_os/server/api.py: app.state.pricing_table singleton exposure so CostAnnotator and the new route read the same PricingTable instance"

requirements-completed:
  - DASH-4-01  # cost-by-agent panel on Observability tab
  - DASH-4-02  # latency p50/p95 panel + tool reliability panel on Observability tab
  - DASH-4-03  # Pitfall 10 small-sample render contract on the latency panel
  - DASH-4-05  # /agents tab cost/latency columns + Pitfall 11 NULL render + uncosted-runs tile

# Tech stack
tech-stack:
  added: []
  patterns:
    - "Vanilla JS only (no React, no D3, no chart library); cost-by-agent panel renders a CSS bar chart with inline div widths sized by (cost / max_cost) * 100%"
    - "Tab JS mirrors Phase 27 Adapters tab: setInterval(5000) cleared on tab switch via the existing setTab machinery; idle-tab cost = zero"
    - "Small-sample render contract (Pitfall 10): sample_count < 10 -> td with title='need at least 10 runs for percentile' and em-dash content, never 0ms, never a percentile number"
    - "Pre-v0.4 NULL render contract (Pitfall 11): total_cost_usd === null -> td with title='no cost data captured before v0.4' and em-dash content across cost AND both latency cells; mixed case (cost present, latency null) renders a different hover so 'no data yet' is distinguishable from 'pre-v0.4'"
    - "Uncosted-runs explanatory tile: sum(uncosted_runs) across all agents via Array.reduce; tile only renders when sum > 0; copy '{N} runs from before v0.4 (no cost data)'"
    - "Pricing-staleness banner (Pitfall 5) with three-color threshold: < 30 days no banner, 30-89 yellow, 90+ red; copy includes HORUS_OS_PRICING_PATH verbatim so the cure path is one cp-and-edit operation away; banner failure is silent so a slow pricing-status route never blocks the panels"
    - "Window selector drives all three observability panels: <select id='obs-window'> with 24h / 7d (selected default) / 30d; change handler re-runs loadObservability"
    - "Em-dash Unicode character (U+2014) appears only inside JS string literals (the render-time representation per Pitfall 10/11 contract), never inside code comments (project no-em-dash-in-prose rule)"
    - "Backend route uses datetime.now(UTC) per codebase convention (storage.py, queries.py, bus.py); not the deprecated datetime.utcnow()"
    - "app.state.pricing_table singleton guards against silent dual-construction so the banner cannot disagree with what the CostAnnotator actually used for cost math (T-36-06 mitigation)"

# Key files
key-files:
  created:
    - tests/test_server_pricing_status.py
    - tests/test_dashboard_observability.py
    - tests/test_dashboard_agents_extension.py
    - tests/test_dashboard_pricing_banner.py
    - .planning/phases/36-observability-dashboard-tab/36-01-SUMMARY.md
  modified:
    - src/horus_os/server/static/index.html
    - src/horus_os/server/api.py

# Metrics
duration: 90m
completed: 2026-05-26
total-tests: 607 passed
commits: 9
---

# Phase 36 Plan 01 Summary: Observability dashboard tab

## What shipped

Nine atomic commits (8 task RED/GREEN pairs plus this summary) deliver the user-visible Observability surface that turns the Phase 32-35 captured data into something an operator actually reads. A 6th tab on the existing single-page dashboard renders three panels (cost-by-agent CSS bar chart, latency p50/p95 table, tool reliability table) driven by a window selector. The /agents tab gains four new columns (cost, p50 ms, p95 ms, uncosted) sourced from the Phase 35 backend extension. A pricing-staleness banner fires at 30 days yellow and 90 days red with copy that names HORUS_OS_PRICING_PATH verbatim so the cure path is one cp-and-edit operation away. All three documented dishonesty pitfalls have render-layer mitigations: Pitfall 10 (sample_count < 10 renders em-dash, never 0ms), Pitfall 11 (pre-v0.4 NULL renders em-dash plus an explanatory tile, never $0), Pitfall 5 (stale pricing.json triggers the colored banner with the override path baked in).

No new dependencies. Zero touches to the locked anti-scope file list. All five v0.3 dashboard surfaces (Chat SSE, Traces explorer, Agents original 5 columns, Writes audit, Adapters tab + polling) continue working byte-identical, pinned by regression-guard tests.

| Commit  | Type        | Title                                                                                            |
| ------- | ----------- | ------------------------------------------------------------------------------------------------ |
| ac58f50 | test(36)    | Task 1 RED: failing tests for /api/observability/pricing-status route                            |
| 4ac9f80 | feat(36)    | Task 1 GREEN: /api/observability/pricing-status route + app.state.pricing_table exposure         |
| 8182d5b | test(36)    | Task 2 RED: failing tests for Observability tab skeleton + Pitfall 10 render                     |
| e745054 | feat(36)    | Task 2 GREEN: Observability tab skeleton + 3 panels + Pitfall 10 small-sample render             |
| 3c185f3 | test(36)    | Task 3 RED: failing tests for /agents tab cost/latency extension + Pitfall 11                    |
| 6327641 | feat(36)    | Task 3 GREEN: /agents tab cost/latency columns + Pitfall 11 NULL render + uncosted tile          |
| 5a8f1c9 | test(36)    | Task 4 RED: failing tests for pricing-staleness banner (Pitfall 5)                               |
| 8defb42 | feat(36)    | Task 4 GREEN: renderStalenessBanner with 3-color thresholds + override-path copy                 |

## Requirements satisfied

- **DASH-4-01** (cost-by-agent panel on Observability tab): Task 2. `renderCostPanel` renders one CSS bar per agent with width sized as `(cost / max_cost) * 100%`; agents with `total_cost_usd === null` render width 0 plus em-dash label (Pitfall 11 honesty). Empty window renders the documented empty state. Pinned by `tests/test_dashboard_observability.py::test_observability_js_function_names_and_api_paths` (function name + API path present) and `::test_observability_three_panel_container_markers` (container id present).
- **DASH-4-02** (latency p50/p95 panel + tool reliability panel): Task 2. `renderLatencyPanel` renders a single-row table with sample_count, p50, p95; `renderToolsPanel` renders a per-tool table with tool_name, call_count, success_rate, last_error_type. Both panels drive off the window selector via the shared `loadObservability()` loader. Pinned by `tests/test_dashboard_observability.py::test_observability_js_function_names_and_api_paths` and `::test_observability_three_panel_container_markers`.
- **DASH-4-03** (Pitfall 10 small-sample render): Task 2. `renderLatencyPanel` checks `data.sample_count < 10` and renders both p50 and p95 cells as `<td title="need at least 10 runs for percentile">` containing the Unicode em-dash character instead of numeric ms values. The grep gate `sample_count < 10` returns 3 occurrences and the hover string returns 2 (one per cell). Pinned by `tests/test_dashboard_observability.py::test_observability_pitfall_10_small_sample_render`.
- **DASH-4-05** (/agents tab cost/latency columns + Pitfall 11 NULL + uncosted tile): Task 3. Four new columns inserted between name and default_model so cost/latency sit adjacent to agent identity. Pre-v0.4 rows (`total_cost_usd === null`) render em-dash with hover `no cost data captured before v0.4` across cost and both latency cells. Explanatory tile above the table sums uncosted_runs across all agents via `Array.reduce` and shows `N runs from before v0.4 (no cost data)` only when sum > 0. v0.3 columns preserved. Pinned by `tests/test_dashboard_agents_extension.py` (all 6 tests).

## ROADMAP Success Criteria

- [x] **SC1 (DASH-4-01, DASH-4-02):** `/observability` tab renders 3 panels (cost-by-agent bar chart, latency p50/p95 table, tool reliability list) with a window selector driving all three. Pinned by `tests/test_dashboard_observability.py::test_observability_three_panel_container_markers` + `::test_observability_window_selector_markers`. [Task 2]
- [x] **SC2 (DASH-4-03, Pitfall 10):** Percentile cells with `sample_count < 10` render em-dash with hover text `need at least 10 runs for percentile`; never as a number, never as `0ms`. Pinned by `::test_observability_pitfall_10_small_sample_render`. [Task 2]
- [x] **SC3 (DASH-4-05, Pitfall 11):** Pre-v0.4 trace rows in the /agents table render em-dash for cost and latency cells with hover text `no cost data captured before v0.4`; separate tile shows `N runs from before v0.4 (no cost data)`. Pinned by `tests/test_dashboard_agents_extension.py::test_agents_tab_pitfall_11_hover_copy` + `::test_agents_tab_uncosted_tile_present` + `::test_agents_tab_null_render_branch_present`. [Task 3]
- [x] **SC4 (Pitfall 5):** Pricing-staleness banner renders when `pricing.json.updated_at > 30 days old`; yellow at 30-89 days, red at 90+; copy includes `Override via HORUS_OS_PRICING_PATH`. Pinned by `tests/test_dashboard_pricing_banner.py::test_banner_render_function_and_override_copy` + `::test_pricing_status_integration_stale_fixture`. [Tasks 1 + 4]
- [x] **SC5 (DASH-4-04 frontend half + v0.3 backward-compat):** `/agents` tab shows the new `total_cost_usd`, `latency_p50_ms`, `latency_p95_ms`, `uncosted_runs` columns sourced from Phase 35; v0.3 surfaces keep working unchanged. Pinned by `tests/test_dashboard_agents_extension.py::test_agents_tab_v03_columns_preserved` + `tests/test_dashboard_observability.py::test_observability_v03_regression_guard` + existing `tests/test_dashboard_adapters.py` (Phase 27 contract still green). [Tasks 2 + 3]

## Pitfalls guarded

| Pitfall | Owner Task | Pin Test |
|---------|-----------|----------|
| Pitfall 5 (pricing-staleness banner; override-path copy verbatim) | Tasks 1 + 4 | `tests/test_dashboard_pricing_banner.py::test_banner_render_function_and_override_copy` (verbatim `HORUS_OS_PRICING_PATH` token + thresholds 30 and 90); `::test_pricing_status_integration_stale_fixture` (env-override fixture flows through to is_stale=True end-to-end, T-36-06 mitigation); `tests/test_server_pricing_status.py::test_pricing_status_honors_env_override` (route-level integration with the same env override) |
| Pitfall 10 (small-sample percentile renders em-dash, never 0ms) | Task 2 | `tests/test_dashboard_observability.py::test_observability_pitfall_10_small_sample_render` (verbatim hover string `need at least 10 runs for percentile` + `sample_count < 10` JS guard + em-dash render character) |
| Pitfall 11 (pre-v0.4 NULL renders em-dash + explanatory tile, never $0) | Task 3 | `tests/test_dashboard_agents_extension.py::test_agents_tab_pitfall_11_hover_copy` (verbatim hover `no cost data captured before v0.4`); `::test_agents_tab_null_render_branch_present` (`total_cost_usd === null` JS guard); `::test_agents_tab_uncosted_tile_present` (tile container + copy `runs from before v0.4`); `::test_agents_tab_uncosted_runs_sum_logic` (per-row reference + reduce() across rows) |

## Anti-scope held

`git diff --stat main..HEAD` against the forbidden file list returns ZERO lines changed in any of:

- `src/horus_os/observability/bus.py`
- `src/horus_os/observability/persist.py`
- `src/horus_os/observability/cost.py`
- `src/horus_os/observability/pricing.py`
- `src/horus_os/observability/pricing.json`
- `src/horus_os/observability/queries.py`
- `src/horus_os/agent.py`
- `src/horus_os/tools/loop.py`
- `src/horus_os/storage.py`
- `pyproject.toml`

No new JS dependencies. No charting library or framework. No new CSS framework (inline CSS only, reuses existing `--accent`, `--border`, `--text-muted`, `--error` vars). No CLI files (Phase 37). No opentelemetry references (Phase 38). The `grep -rE 'chart\.js|d3\.js|react|vue|svelte' src/horus_os/server/static/index.html` gate returns zero matches.

## Threat register outcomes

- **T-36-01** (Information Disclosure, last_error_type rendering): **mitigated**. `renderToolsPanel` renders only `tool_name`, `call_count`, `success_rate`, `last_error_type`; the file-content substring `last_error_message` and `error_text` are both absent from index.html. The Phase 35 backend already strips the text-content error column at the query layer; this task adds no new column reads.
- **T-36-02** (Information Disclosure, agent names + dollar amounts): **accepted** per register. Localhost-bound; non-PII metadata; no auth surface in v0.4.
- **T-36-03** (Tampering, obs-window selector value): **mitigated**. The selector is a fixed `<select>` with three hardcoded options. Even if a hand-crafted request supplies a malformed `?since=`, the backend `parse_window` rejects it with `HTTPException(400)` and all SQL uses `?` placeholders (Phase 35 contract).
- **T-36-04** (DoS, 5-second poll cadence): **mitigated**. `observabilityPoll` is only set when the Observability tab becomes active and is cleared in `setTab` whenever the user switches away. Idle-tab cost = zero. Active-tab cost = 4 fetches per 5 seconds against indexed `created_at` columns from Phase 32. Pinned by `tests/test_dashboard_observability.py::test_observability_setTab_dispatch_and_poll_cleanup`.
- **T-36-05** (Information Disclosure, updated_at_age_days): **accepted** per register. An integer day count over a file shipped publicly in the wheel reveals nothing the wheel itself does not.
- **T-36-06** (Spoofing, banner claims an override path that might not work): **mitigated**. `tests/test_server_pricing_status.py::test_pricing_status_honors_env_override` and `tests/test_dashboard_pricing_banner.py::test_pricing_status_integration_stale_fixture` both prove end-to-end that the `HORUS_OS_PRICING_PATH` env override the banner advertises actually changes the route's response. If the override silently broke, the tests would fail before the banner ever shipped.
- **T-36-07** (Information Disclosure, uncosted-runs aggregate): **accepted** per register. The tile sums an integer count of pre-v0.4 traces; no per-trace content reaches the tile.

## Deviations from plan

None of substance. Two minor adjustments tracked inside their owner commits, not as separate deviations:

1. **datetime convention follow-the-codebase fix (Task 1 GREEN).** The plan's behavioral description suggested `datetime.utcnow()`. The actual codebase uses `datetime.now(UTC)` across `storage.py`, `queries.py`, `bus.py`, and `notes.py` (and `datetime.utcnow()` is deprecation-warned in Python 3.12). The Task 1 commit switched to `datetime.now(UTC)` to match the convention; the behavioral contract (same Date / age / staleness output) is unchanged because both compute the same wall-clock instant.

2. **Mixed-case latency render branch (Task 3 GREEN).** The plan describes the Pitfall 11 NULL render for the cost cell and notes that when cost is present but latency is null (no llm_calls rows landed yet for the rollup), the cells should render em-dash with a different hover. The implementation honors this distinction explicitly: pre-v0.4 NULL renders em-dash with hover `no cost data captured before v0.4` across cost AND both latency cells; the mixed case renders em-dash with hover `need at least 1 llm_calls row` so operators can distinguish "no data yet" from "pre-v0.4." This was implicit in the plan; the implementation makes it explicit at the JS code level.

No architectural Rule 4 deviations. No new dependencies. No touches to anti-scope files.

## Authentication gates

None encountered. All tests run against in-process FastAPI fixtures with `TestClient(create_app(data_dir=tmp_path))`. No real HTTP calls and no external services. The `HORUS_OS_PRICING_PATH` env override flows through `monkeypatch.setenv` to a fixture pricing.json on the test's `tmp_path`; no shared filesystem state.

## Test counts

- Before Phase 36: 585 passed (per Phase 35 SUMMARY).
- After Phase 36: **607 passed, 0 failed, 0 skipped** (22 new tests across 4 new test files).

| New test file                              | Test count | Covers                                                                                                                                                                                                       |
|--------------------------------------------|-----------:|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| tests/test_server_pricing_status.py        | 4          | Task 1: response shape + JSON content-type + app.state.pricing_table singleton + HORUS_OS_PRICING_PATH env override flows end-to-end                                                                          |
| tests/test_dashboard_observability.py      | 7          | Task 2: 6th tab nav + section + window selector + 3 panel containers + JS function names + API paths + setTab dispatch + Pitfall 10 small-sample render + v0.3 5-tab regression guard                         |
| tests/test_dashboard_agents_extension.py   | 6          | Task 3: 4 new column headers + Pitfall 11 hover copy + uncosted tile container + NULL render JS branch + uncosted_runs reduce() sum logic + v0.3 5-column backward-compat                                     |
| tests/test_dashboard_pricing_banner.py     | 5          | Task 4: renderStalenessBanner JS function + verbatim HORUS_OS_PRICING_PATH copy + endpoint reference + thresholds 30 and 90 + .obs-banner.yellow/.red CSS classes + integration with stale fixture + bundled-file freshness self-consistency check |

## Out of scope (deliberate)

- **Backend write path (`bus.py`, `persist.py`, `cost.py`)**: untouched. Phases 33-34 own these; Phase 36 is read-only at the route layer (new `/api/observability/pricing-status` reads `app.state.pricing_table`).
- **Pricing data (`pricing.py`, `pricing.json`)**: untouched. Phase 34 owns the substrate; Phase 36 only displays metadata.
- **Query module (`queries.py`)**: untouched. Phase 35 shipped the four query primitives + `agent_totals`; Phase 36 only consumes them via the existing routes.
- **Agent runner (`agent.py`, `tools/loop.py`)**: untouched.
- **Storage (`storage.py`)**: untouched. Schema v5 from Phase 32 has every column this plan reads.
- **`pyproject.toml`**: untouched. No new dependencies (no charting library, no framework, no JS package).
- **Phase 37 CLI `horus-os usage`**: out of scope. The query module returns the same data shapes; the human-readable rendering and column formatting lives in Phase 37.
- **Phase 38 OpenTelemetry adapter**: zero opentelemetry references introduced.
- **Per-window `/api/agents`**: untouched. The existing route hardcodes a 7d rollup window per Phase 35 backward-compat; if a future need surfaces, that is a follow-up.

## Forward dependencies for Phase 37 (CLI)

The CLI's `horus-os usage` subcommand will read from the same `/api/observability/*` routes (or directly from `queries.py`) that the Observability tab now consumes. Because both surfaces share the query module and the JSON envelope shape, the Pitfall 10 / 11 contracts surface uniformly: the CLI applies the same `sample_count < 10` rule for percentiles and the same `total_cost_usd is None` branch for pre-v0.4 traces. The dashboard's verbatim hover copy gives Phase 37 the same canonical strings to print for its `--format=table` mode.

Phase 38's OpenTelemetry adapter will not change the `/api/observability/pricing-status` route because pricing staleness is a local concern, not an OTel one.

## Self-Check

Verified before declaring this plan complete:

1. **All 9 commits exist on the branch** (`git log --oneline main..HEAD | wc -l` returns 9 including this summary commit when made).
2. **All 4 created test files exist** at their canonical paths under `tests/`.
3. **Both modified files contain the documented markers**:
   - `src/horus_os/server/api.py`: contains `app.state.pricing_table` and `@app.get("/api/observability/pricing-status")` (grep both return >= 1).
   - `src/horus_os/server/static/index.html`: contains all of `data-tab="observability"` (1), `id="observability"` (1), `observabilityPoll` (5), `need at least 10 runs for percentile` (2), `sample_count < 10` (3), `no cost data captured before v0.4` (3), `total_cost_usd === null` (4), `runs from before v0.4` (1), `renderStalenessBanner` (2), `HORUS_OS_PRICING_PATH` (2), `/api/observability/pricing-status` (1), `Pricing data is` (1), `< 30` (1), `< 90` (1).
4. **Pytest:** `.venv/bin/python -m pytest tests/ -q` exits 0 with **607 passed**.
5. **Ruff:** `.venv/bin/ruff check src/ tests/` exits 0; `.venv/bin/ruff format --check src/ tests/` exits 0.
6. **No-wallclock lint:** `.venv/bin/python scripts/lint_no_wallclock.py` exits 0.
7. **Anti-scope:** `git diff --stat main..HEAD` against the locked file list returns 0 lines.
8. **No new dependencies:** `git diff main..HEAD -- pyproject.toml` returns empty.
9. **No JS framework / charting library:** `grep -rE 'chart\.js|d3\.js|react|vue|svelte' src/horus_os/server/static/index.html` returns 0 matches.
10. **Em-dash hygiene:** the U+2014 Unicode character appears only inside JS string literals (the Pitfall 10/11 render contract), never inside code comments. Verified by inspecting all 9 occurrences in index.html.

Self-Check: PASSED
