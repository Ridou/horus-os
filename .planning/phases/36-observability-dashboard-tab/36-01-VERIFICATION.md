---
phase: 36-observability-dashboard-tab
verified: 2026-05-26T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 36: Observability Dashboard Tab — Verification Report

**Phase Goal:** New `/observability` tab + 3 panels (cost-by-agent, latency p50/p95, tool reliability) + window selector + small-sample handling (Pitfall 10) + pre-v0.4 NULL render (Pitfall 11) + pricing-staleness banner (Pitfall 5). Vanilla JS only.
**Verified:** 2026-05-26
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| #  | Truth                                                                                                                                                                                                                                       | Status     | Evidence                                                                                                                                                                                                |
| -- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SC1 | `/observability` tab renders 3 panels (cost-by-agent CSS bar chart, latency p50/p95 table, tool reliability list) with window selector (24h/7d/30d, default 7d) driving all three (DASH-4-01, DASH-4-02)                                       | VERIFIED   | index.html:84 (`<button data-tab="observability">`), :128 (`<section ... id="observability">`), :132 (`<select id="obs-window">`), :140/:144/:148 (three `obs-*-panel` divs). `renderCostPanel/renderLatencyPanel/renderToolsPanel` JS functions present and substantive (lines 533, 552, 571). All driven by `loadObservability()` (line 488). |
| SC2 | Percentile cells with `sample_count < 10` render em-dash with hover "need at least 10 runs for percentile"; never a number, never `0ms` (DASH-4-03, Pitfall 10)                                                                                  | VERIFIED   | grep `sample_count < 10` returns 3; grep `need at least 10 runs` returns 2; em-dash U+2014 confirmed in body. Pinned by `test_observability_pitfall_10_small_sample_render`.                                                  |
| SC3 | Pre-v0.4 trace rows in `/agents` render em-dash for cost+latency cells with hover "no cost data captured before v0.4"; separate tile shows "N runs from before v0.4 (no cost data)" (DASH-4-05, Pitfall 11)                                          | VERIFIED   | grep `total_cost_usd === null` returns 4; grep `no cost data captured before v0.4` returns 3; tile container `id="agents-uncosted-tile"` present (line 109); reduce() sum at line 406; show/hide gate `totalUncosted > 0` at line 407. Pinned by 6/6 tests in `test_dashboard_agents_extension.py`.                                                              |
| SC4 | Pricing-staleness banner renders when `pricing.json.updated_at > 30 days` old; yellow 30-89, red 90+; copy includes `HORUS_OS_PRICING_PATH` verbatim (Pitfall 5)                                                                                     | VERIFIED   | `renderStalenessBanner` defined (line 515); thresholds `< 30` and `< 90` present; CSS `.obs-banner.yellow` and `.obs-banner.red` defined (lines 64-65); copy "Pricing data is " + age + " days old. Override via HORUS_OS_PRICING_PATH." at line 525. Backend route `/api/observability/pricing-status` at api.py:392 reads `app.state.pricing_table.is_stale(now, 30)`. End-to-end env override pinned by `test_pricing_status_honors_env_override` + `test_pricing_status_integration_stale_fixture`. |
| SC5 | `/agents` tab shows new `total_cost_usd`, `latency_p50_ms`, `latency_p95_ms`, `uncosted_runs` columns from Phase 35; v0.3 surfaces keep working unchanged                                                                                          | VERIFIED   | All four new column headers (`>cost</th>`, `>p50 ms</th>`, `>p95 ms</th>`, `>uncosted</th>`) present in index.html. All five v0.3 columns (`name`, `default_model`, `allowed_tools`, `last_activity_at`, `system_prompt`) preserved. `tests/test_dashboard_adapters.py` (Phase 27 v0.3 contract) still passes 2/2. v0.3 regression-guard test in `test_dashboard_observability.py` asserts five existing tab nav buttons + adaptersPoll still present. |

**Score:** 5/5 truths verified

### Grep Gate Verification

| # | Gate | Expected | Actual | Status |
|---|------|----------|--------|--------|
| 1 | `<button data-tab="observability">` in index.html | 1 | 1 | VERIFIED |
| 2 | `id="observability"` in index.html | >= 1 | 1 | VERIFIED |
| 3 | `id="obs-window"` in index.html | 1 | 1 | VERIFIED |
| 4 | `need at least 10 runs` in index.html | >= 1 | 2 | VERIFIED |
| 5 | `no cost data captured before v0.4` in index.html | >= 1 | 3 | VERIFIED |
| 6 | `HORUS_OS_PRICING_PATH` in index.html | >= 1 | 2 | VERIFIED |
| 7 | `/api/observability/pricing-status` in api.py | 1 | 1 | VERIFIED |
| 8 | `chart.js|d3.js|react|vue|svelte` in index.html | 0 | 0 | VERIFIED |

### Required Artifacts

| Artifact                                                  | Expected                                              | Status     | Details                                                                                  |
| --------------------------------------------------------- | ----------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------- |
| `src/horus_os/server/static/index.html`                    | 6th tab + 3 panels + selector + render contracts      | VERIFIED   | 598 lines (vs ~330 baseline); all markers + JS functions present and substantive          |
| `src/horus_os/server/api.py`                                | new pricing-status route + `app.state.pricing_table` | VERIFIED   | 847 lines; route at line 392; app.state exposure at line 143; diff is surgical (+22 lines)|
| `tests/test_dashboard_observability.py`                    | new test file (7 tests)                               | VERIFIED   | 119 lines, 7/7 pass                                                                       |
| `tests/test_dashboard_agents_extension.py`                | new test file (6 tests)                               | VERIFIED   | 80 lines, 6/6 pass                                                                        |
| `tests/test_dashboard_pricing_banner.py`                   | new test file (5 tests)                               | VERIFIED   | 113 lines, 5/5 pass                                                                       |
| `tests/test_server_pricing_status.py`                      | new test file (4 tests)                               | VERIFIED   | 114 lines, 4/4 pass                                                                       |

### Key Link Verification

| From                                                | To                                                     | Via                                                                          | Status |
| --------------------------------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------- | ------ |
| Tab nav button (`data-tab="observability"`)         | `<section id="observability">`                          | shared `setTab(name)` machinery; `name === "observability"` branch present  | WIRED  |
| `loadObservability()`                                | `/api/observability/{cost,latency,tools}`               | three `fetch(url + qs)` calls then `renderCostPanel/Latency/Tools`           | WIRED  |
| `renderStalenessBanner()`                            | `/api/observability/pricing-status`                     | `fetch('/api/observability/pricing-status')` -> banner HTML                  | WIRED  |
| `/api/observability/pricing-status` route           | `PricingTable` singleton                                | `app.state.pricing_table` (same instance the `CostAnnotator` subscriber holds, pinned by `test_app_state_pricing_table_is_singleton`)            | WIRED  |
| Agents tab render                                    | `total_cost_usd` / `latency_p50_ms` / `latency_p95_ms` / `uncosted_runs` | `loadAgents` -> `fetch('/api/agents')` -> per-row null-aware render + `Array.reduce` for tile           | WIRED  |
| Window selector change                               | `loadObservability`                                     | `obs-window.addEventListener("change", loadObservability)` at line 589        | WIRED  |
| Tab switch                                           | 5s poll cleanup                                         | `clearInterval(observabilityPoll)` in `setTab` (line 183)                    | WIRED  |

### Data-Flow Trace (Level 4)

| Artifact / Variable                | Data Source                                                                                          | Real Data | Status |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------- | --------- | ------ |
| Cost panel (`renderCostPanel`)     | `/api/observability/cost?since={window}` -> `cost_by_agent` SQL query (Phase 35, real `traces` rollup) | Yes       | FLOWING |
| Latency panel (`renderLatencyPanel`) | `/api/observability/latency?since={window}` -> `latency_p50_p95` SQL with `NTILE(100)` (Phase 35)     | Yes       | FLOWING |
| Tools panel (`renderToolsPanel`)   | `/api/observability/tools?since={window}` -> `tool_reliability` SQL (Phase 35)                       | Yes       | FLOWING |
| Staleness banner                   | `/api/observability/pricing-status` -> `app.state.pricing_table.is_stale(now, 30)` (Phase 34)         | Yes       | FLOWING |
| Agents tab cost/latency cells      | `/api/agents` extended in Phase 35 with `total_cost_usd`, `latency_p50_ms`, `latency_p95_ms`, `uncosted_runs` from real rollup | Yes       | FLOWING |
| Uncosted tile                      | `data.agents.reduce(...)` over `uncosted_runs` from `/api/agents`                                    | Yes       | FLOWING |

All wired artifacts trace upstream to real SQL queries from Phases 32-35. No hollow props, no static fallbacks, no hardcoded empty arrays at the call site.

### Behavioral Spot-Checks

| Behavior                                              | Command                                                                                       | Result     | Status |
| ----------------------------------------------------- | --------------------------------------------------------------------------------------------- | ---------- | ------ |
| All 4 new Phase 36 test files pass                    | `pytest tests/test_dashboard_observability.py tests/test_dashboard_agents_extension.py tests/test_dashboard_pricing_banner.py tests/test_server_pricing_status.py` | 22 passed  | PASS   |
| Full test suite passes (607+ tests)                   | `pytest tests/ -q`                                                                            | 607 passed | PASS   |
| v0.3 Adapters tab regression (Phase 27 contract)      | `pytest tests/test_dashboard_adapters.py -q`                                                  | 2 passed   | PASS   |
| Static dashboard HTML served (200) with all 6 tab nav buttons | `TestClient(create_app(...)).get("/")` -> 200 with all markers | 200 + markers | PASS (covered by tests above) |
| `/api/observability/pricing-status` returns documented shape | `TestClient.get("/api/observability/pricing-status")` -> `{updated_at, updated_at_age_days, is_stale}` | OK         | PASS (pinned by `test_pricing_status_returns_expected_shape`) |
| Env override `HORUS_OS_PRICING_PATH` flows end-to-end | `monkeypatch.setenv` + GET -> matches fixture `updated_at`                                     | OK         | PASS (pinned by `test_pricing_status_honors_env_override`) |

### Requirements Coverage

| Requirement | Source Plan | Description                                                                            | Status     | Evidence                                                                                                    |
| ----------- | ----------- | --------------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------- |
| DASH-4-01   | 36-01       | New `/observability` tab with three panels                                              | SATISFIED  | Tab + section + 3 panel containers present; `renderCostPanel/Latency/Tools` JS functions populated         |
| DASH-4-02   | 36-01       | Window selector (24h/7d/30d, default 7d) drives all panels                              | SATISFIED  | `<select id="obs-window">` with all 3 options, `value="7d" selected`; change handler re-runs loader        |
| DASH-4-03   | 36-01       | Percentile cells with n < 10 render as em-dash, not number                              | SATISFIED  | `sample_count < 10` guard renders em-dash with verbatim hover string                                       |
| DASH-4-05   | 36-01       | Pre-v0.4 trace rows render em-dash with verbatim hover + explanatory tile               | SATISFIED  | `total_cost_usd === null` branch + 4 new column headers + tile container + reduce()-based show/hide gate    |

DASH-4-04 (backend half of /agents extension) belongs to Phase 35 per REQUIREMENTS.md row 224 and is consumed by this phase's frontend.

### Anti-Patterns Found

None. Modified files contain:
- Zero `TBD|FIXME|XXX` debt markers
- Zero `TODO|HACK|PLACEHOLDER|not yet implemented|coming soon` cleanup comments
- Zero `return null/{}/[]` stub returns
- Zero new dependencies (pyproject.toml diff is empty)
- Zero `chart.js|d3.js|react|vue|svelte` JS-framework references

### Anti-Scope Verification

`git diff 815850e..HEAD --name-only | grep -E '(bus|persist|cost|pricing|queries|agent|tools|storage)\.py|pyproject'` returns ZERO matches. Files touched:

- `.planning/phases/36-observability-dashboard-tab/36-01-SUMMARY.md` (allowed)
- `src/horus_os/server/api.py` (allowed)
- `src/horus_os/server/static/index.html` (the dashboard, allowed)
- `tests/test_dashboard_agents_extension.py` (new test, allowed)
- `tests/test_dashboard_observability.py` (new test, allowed)
- `tests/test_dashboard_pricing_banner.py` (new test, allowed)
- `tests/test_server_pricing_status.py` (new test, allowed)

`bus.py`, `persist.py`, `cost.py`, `pricing.py`, `queries.py`, `agent.py`, `tools/loop.py`, `storage.py`, `pyproject.toml`: untouched.

### Pitfall Coverage

| Pitfall                                                                         | Owner Task   | Pin Test                                                                                                   | Status |
| ------------------------------------------------------------------------------- | ------------ | ---------------------------------------------------------------------------------------------------------- | ------ |
| Pitfall 5 (pricing-staleness banner; override-path copy verbatim)               | Tasks 1 + 4 | `test_banner_render_function_and_override_copy`, `test_pricing_status_integration_stale_fixture`, `test_pricing_status_honors_env_override` | VERIFIED |
| Pitfall 10 (small-sample percentile renders em-dash, never 0ms)                 | Task 2      | `test_observability_pitfall_10_small_sample_render`                                                       | VERIFIED |
| Pitfall 11 (pre-v0.4 NULL renders em-dash + explanatory tile, never $0)         | Task 3      | `test_agents_tab_pitfall_11_hover_copy`, `test_agents_tab_null_render_branch_present`, `test_agents_tab_uncosted_tile_present` | VERIFIED |

### Gaps Summary

No gaps. Phase 36 ships its observability surface end-to-end. All 5 ROADMAP Success Criteria verified against the codebase, all 11 verification-context gates pass, all 22 new tests green, full 607-test suite green, anti-scope held, zero new dependencies, zero anti-patterns. The pricing-staleness banner's env-override path (`HORUS_OS_PRICING_PATH`) is integration-tested end-to-end so the banner cannot lie about the cure path (T-36-06 mitigation). The `app.state.pricing_table` singleton guards against silent dual-construction so the banner cannot disagree with what the CostAnnotator actually used.

---

## VERIFICATION PASSED

| Truth | Status |
|-------|--------|
| SC1 (3 panels + window selector) | VERIFIED |
| SC2 (Pitfall 10 small-sample em-dash) | VERIFIED |
| SC3 (Pitfall 11 pre-v0.4 NULL + tile) | VERIFIED |
| SC4 (Pitfall 5 pricing-staleness banner) | VERIFIED |
| SC5 (/agents cost/latency columns + v0.3 backward-compat) | VERIFIED |

_Verified: 2026-05-26_
_Verifier: Claude (gsd-verifier)_
