---
phase: 45-rest-api-plugins-dashboard-observability
plan: 01
subsystem: server
tags: [rest-api, dashboard, observability, plugins, security]
dependency-graph:
  requires: [44]
  provides: [45-01-rest-surface, 45-01-dashboard-tab, 45-01-per-plugin-observability]
  affects: [46, 47]
tech-stack:
  added: []
  patterns:
    - APIRouter mounted via app.include_router (decoupled from create_app closure)
    - Per-request Database(cfg.db_path) (mirrors list_traces handler)
    - Pydantic v2 frozen models with Literal types mirroring SQLite CHECK constraints
    - DOM sanitation via escapeHtml + textContent + safeUrl URL-scheme gate
key-files:
  created:
    - src/horus_os/server/schemas.py
    - src/horus_os/server/plugins_api.py
    - tests/server/__init__.py
    - tests/server/test_observability_plugins.py
    - tests/server/test_plugins_api.py
    - tests/server/test_dashboard_plugins.py
    - tests/plugins/test_dashboard_hyperlinks_sanitized.py
  modified:
    - src/horus_os/observability/queries.py
    - src/horus_os/server/api.py
    - src/horus_os/server/static/index.html
decisions:
  - APIRouter in a dedicated module so api.py stays under 1200 lines (1113 after this plan)
  - app.state.data_dir exposed so the router resolves Config per-request without closure-capturing data_dir
  - SQLite FULL OUTER JOIN with a UNION fallback for older SQLite versions (< 3.39) when computing per_plugin_rollup
  - Pitfall 10 (n<10 percentile) applied in Python (not SQL) so the dashboard receives null rather than misleading small-sample numbers
  - Pitfall 11 (NULL cost stays None, never 0) preserved through Pydantic's Optional[float] typing
  - T-45-01: actor='dashboard' hard-coded in grant/revoke routes; never accepted from request body
  - T-45-02 / T-45-07: every manifest-sourced string flows through escapeHtml or textContent; URL fields gated on safeUrl (startsWith http:// or https://)
metrics:
  duration: 11m 18s
  completed: 2026-05-26
---

# Phase 45 Plan 01: REST API + /plugins dashboard tab + per-plugin observability Summary

Six `/api/plugins/*` routes + one `/api/observability/plugins` route + `/plugins` dashboard tab + by-plugin obs tile + DASH-5-03 sanitation regression test.

## What Shipped

1. **REST surface (Task 2)** -- Six routes: `GET /api/plugins`, `GET /api/plugins/{name}`, `POST /api/plugins/{name}/enable`, `POST /api/plugins/{name}/disable`, `POST /api/plugins/{name}/grant`, `DELETE /api/plugins/{name}/grant/{capability}`. Each route reads `request.app.state.plugin_registry` and re-opens `Database(cfg.db_path)` per request (mirrors the list_traces handler pattern). T-45-01 mitigation: `actor='dashboard'` hard-coded on grant/revoke; never accepted from request body.

2. **Per-plugin observability (Task 1 + 2)** -- `per_plugin_rollup(db, window)` appended to `observability/queries.py` (NTILE(100) partitioned by `COALESCE(plugin_name, 'horus-os core')`). Exposed via `GET /api/observability/plugins?since=7d|30d`. Pitfall 10 (n<10 -> None) applied in Python; Pitfall 11 (NULL cost stays None, never 0) honored.

3. **Pydantic schemas (Task 1)** -- Five frozen models in `src/horus_os/server/schemas.py`: PluginInfo, PluginInfoDetailed, PluginCapabilityState, PluginObservabilityRollup, PluginGrantLogEntry. Every model `ConfigDict(extra='forbid', frozen=True)`; Literal types mirror SQLite CHECK constraints.

4. **/plugins dashboard tab (Task 3)** -- One nav button, one tab section, one card-style render path (`renderPluginTile`), one 10s setInterval poll. Cloned the loadAdapters shape verbatim with name substitution. Status badge (loaded=green / pending=yellow / error=red / disabled=muted), declared tool/adapter chips, granted (green) + pending (yellow) capability chips with inline grant/revoke buttons, author + homepage + issue_tracker links (gated on safeUrl), last error preview on hover.

5. **By-plugin observability tile (Task 3)** -- Fourth `obs-panel` inside the `/observability` tab. Renders the `/api/observability/plugins` response as a table with columns `plugin_name | invocations | error_rate | p50 | p95 | cost`. Em-dash rendering for null cells matches the existing tool reliability + cost tile contracts.

6. **DASH-5-03 sanitation (Task 3)** -- The `safeUrl` helper gates homepage / issue_tracker URLs on `startsWith('http://') || startsWith('https://')`. Every manifest-sourced string (name, version, author, homepage, issue_tracker, last_error, declared tool/adapter names, capability strings) flows through `escapeHtml` before reaching `innerHTML`. Regression test pinned at file level: `tests/plugins/test_dashboard_hyperlinks_sanitized.py`.

## Files Created / Modified

**Created (7):**

- `src/horus_os/server/schemas.py` (5 Pydantic v2 frozen models, 218 lines)
- `src/horus_os/server/plugins_api.py` (APIRouter with 7 routes, 261 lines)
- `tests/server/__init__.py` (empty package marker)
- `tests/server/test_observability_plugins.py` (6 tests)
- `tests/server/test_plugins_api.py` (17 tests including byte-identity guard)
- `tests/server/test_dashboard_plugins.py` (2 tests)
- `tests/plugins/test_dashboard_hyperlinks_sanitized.py` (3 tests)

**Modified (3):**

- `src/horus_os/observability/queries.py` -- APPENDED `per_plugin_rollup`; existing 5 exports byte-identical
- `src/horus_os/server/api.py` -- 3 additions: 1-line import, 5-line `app.state.data_dir` block (with comments), 6-line `app.include_router` block (with comments); zero existing handlers modified
- `src/horus_os/server/static/index.html` -- nav button, tab section, 4th obs panel, JS state (`pluginsPoll`), setTab branch, 4 new functions (loadPlugins, renderPluginTile, togglePluginEnable, grantOrRevokeCapability), safeUrl helper, renderObservabilityPlugins helper; no existing tab's JS is touched

## Test Count Delta and Pass Status

Before Phase 45: **888 tests passing** (Phase 44 SUMMARY count)
After Phase 45: **916 tests passing** (+ 28 new tests)

Per-task breakdown:
- Task 1: 6 new tests (`test_observability_plugins.py`)
- Task 2: 17 new tests (`test_plugins_api.py`, includes the byte-identity guard test)
- Task 3: 5 new tests (`test_dashboard_plugins.py` + `test_dashboard_hyperlinks_sanitized.py`)

Pre-existing test suite: **261 server / plugins / observability tests** unchanged and green; full v0.4 byte-identity contract preserved (verified by running `tests/test_server_*.py` + `tests/plugins/` + `tests/observability/` after each task commit).

Ruff: clean across all new files + modifications.

## Deviations from Plan

None substantive. Two minor implementation notes:

1. **SQLite FULL OUTER JOIN fallback** -- The `per_plugin_rollup` query uses a `FULL OUTER JOIN` (SQLite >= 3.39). For older SQLite builds the function catches `sqlite3.OperationalError` and falls back to a `LEFT JOIN + UNION` shape that produces the same result set. Documented in the function's docstring; not a deviation from the plan's contract.

2. **JS chip rendering** -- The grant/revoke buttons live inline within the capability chip (one `<button>` per chip with `data-cap-action="grant"|"revoke"`, `data-name`, `data-capability` attributes), wired via `addEventListener` mirroring the `toggleAdapter` pattern. The plan's "no separate modal element" guidance was respected.

## v0.4 Byte-Identity Guard

Status: **PASS**. The only diff to `src/horus_os/server/api.py` is three additive sections (one import, two `app.state` / `app.include_router` lines with comments). Zero existing route handlers modified. The dedicated byte-identity test in `tests/server/test_plugins_api.py::test_v04_observability_byte_identity` asserts the `/api/observability/cost` response shape stays `{"agents": [...]}`. The Phase 36 test suite (`tests/test_server_pricing_status.py`, `tests/test_server_observability_routes.py`) passes unchanged.

## Phase 46 Hand-Off Note

The six `/api/plugins/*` routes + `/api/observability/plugins` shipped here are the substrate Phase 46's tier-2 e2e tests will consume. The dashboard surface (`renderPluginTile` + `safeUrl` gate + escapeHtml flow) is the user-facing trust boundary for Phase 47's `docs/PLUGIN-SECURITY.md` threat-model section. The `tests/plugins/test_dashboard_hyperlinks_sanitized.py` regression contract is pinned at file level; future dashboard refactors that touch the plugins tab MUST keep the escapeHtml / textContent / safeUrl contract or the gate fails the build.

## Self-Check: PASSED

- src/horus_os/server/schemas.py: FOUND
- src/horus_os/server/plugins_api.py: FOUND
- src/horus_os/observability/queries.py: per_plugin_rollup in __all__: FOUND
- src/horus_os/server/api.py: include_router(plugins_router): FOUND
- src/horus_os/server/static/index.html: data-tab="plugins": FOUND
- src/horus_os/server/static/index.html: obs-plugins-panel: FOUND
- tests/server/test_observability_plugins.py: 6/6 passing
- tests/server/test_plugins_api.py: 17/17 passing
- tests/server/test_dashboard_plugins.py: 2/2 passing
- tests/plugins/test_dashboard_hyperlinks_sanitized.py: 3/3 passing
- Full suite: 916/916 passing
- Ruff clean
- v0.4 byte-identity test: PASS
- Commits 8b12390, aed2964 in git log (Task 1 + Task 2)
