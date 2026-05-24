---
phase: 27-dashboard-adapter-management
plan: "01"
subsystem: dashboard
tags: [dashboard, adapter, lifecycle, toggle, tool-registry, frontend, server]

requires:
  - phase: "22-01"
  - phase: "26-01"
provides:
  - "POST /api/adapters/{name}/disable route driving LifecycleAdapter.stop"
  - "POST /api/adapters/{name}/enable route driving LifecycleAdapter.start"
  - "supports_toggle field on GET /api/adapters per entry"
  - "ToolRegistry wired through AdapterContext at create_app (Phase 26 deferred)"
  - "app.state.tool_registry and app.state.adapters exposed on the FastAPI app"
  - "Dashboard Adapters tab with status pills, last activity, error count, error message, per-adapter toggle, 5s polling"

requirements-completed:
  - DASH-3-01  # /adapters dashboard view lists adapters with status, last activity, error count
  - DASH-3-02  # Enable/disable toggle via POST /api/adapters/{name}/{enable,disable}

duration: ~25m
completed: 2026-05-24
total-tests: 437
delta-tests: +14
v0.3-progress: Phase 27 of 31 complete (DASH-3 group requirements done)
---

# Phase 27 Plan 01 Summary: Dashboard adapter management

## What shipped

The operator control plane for v0.3 adapters. Phase 22 stood up
read-only status reporting. Phase 27 makes it interactive: two
new POST routes for enable and disable, a dashboard tab that
renders live state and exposes a per-adapter toggle button, and
the Phase 26 deferred `tool_registry` wiring so tool-providing
adapters (Calendar today) actually register tools end-to-end.

### Backend

| Route | Behavior |
|-------|----------|
| `POST /api/adapters/{name}/disable` | Calls `await adapter.stop()` on a lifecycle adapter, flips registry to `stopped`. 404 unknown, 400 missing hook, 500 on hook raise with registry error capture |
| `POST /api/adapters/{name}/enable` | Calls `await adapter.start(ctx)`, flips to `running`. Same error semantics as disable |
| `GET /api/adapters` (extended) | Each entry now includes `supports_toggle: bool` derived from `hasattr(start) and hasattr(stop)` |

`create_app` was extended in three places:

1. Builds an `_app_tool_registry = ToolRegistry()` before
   constructing `AdapterContext`.
2. Passes `tool_registry=_app_tool_registry` into the context.
3. Exposes `app.state.tool_registry` (the registry) and
   `app.state.adapters` (the discovered adapter list) on the
   FastAPI app.

The toggle routes look adapters up in `_adapters` by name and
dispatch via `hasattr` for `start`/`stop`, mirroring the
lifespan's pattern. Errors raised by hooks are captured into the
registry via `mark_error` before the route returns 500, so the
dashboard's next poll surfaces the failure with the exception
text.

### Frontend

A fifth nav tab "Adapters" in `static/index.html`. The tab
renders a table:

| Column | Source |
|--------|--------|
| name | `a.name` |
| status | color-coded pill: running green, stopped gray, error red |
| last_activity_at | string or "(never)" |
| errors | `a.error_count` |
| error_message | truncated to 80 chars, full text in the `title` attribute |
| action | "Disable" when running, "Enable" otherwise, "n/a" disabled with tooltip when `supports_toggle` is false |

JS additions: `loadAdapters()` (fetch + render), `toggleAdapter(name, action)`
(POST + refresh), an `adaptersPoll` `setInterval` started on tab
activation and cleared on tab switch via the existing
`setTab(name)` function. New CSS: `.pill.muted` for the stopped
status. No external libraries, no build step.

The v0.2 tabs (Chat, Traces, Agents, Writes) and their JS
surfaces are unchanged.

## Files touched

- `src/horus_os/server/api.py`: tool_registry wiring at
  `create_app`, `app.state.tool_registry` and `app.state.adapters`,
  `supports_toggle` field on `/api/adapters`, two new POST routes
- `src/horus_os/server/static/index.html`: Adapters tab markup,
  `.pill.muted` CSS, `loadAdapters` / `toggleAdapter` JS, polling
- `tests/test_server_adapters.py`: existing payload shape
  assertion extended to six keys; `supports_toggle` asserted on
  the webhook entry
- `tests/test_server_adapters_toggle.py` (new): 14 tests covering
  toggle routes, registry error capture, and tool_registry wiring
- `tests/test_dashboard_adapters.py` (new): 2 build-gate tests
  on the dashboard HTML surface

## Test surface

| File | Tests | Covers |
|------|-------|--------|
| `tests/test_server_adapters_toggle.py` | 12 | 404 unknown name (disable, enable), 400 missing hook (disable, enable), status flip + hook called (disable, enable), 500 + registry error capture (stop raises, start raises), `supports_toggle` shape, `app.state.tool_registry` type, tool-providing adapter registers tool on app state, `app.state.adapters` lists discovered |
| `tests/test_dashboard_adapters.py` | 2 | Adapters tab markers + JS surface present, v0.2 tabs and JS surfaces remain |

437 passed in 4.91s (423 baseline + 14 new). All v0.2 adapter,
server, and dashboard tests pass byte-identical (the one
extended assertion in `test_server_adapters.py` was updated to
match the additive `supports_toggle` field).

## Lint status

`ruff check .` clean. `ruff format --check .` clean. One
auto-fix run was needed during the test commit (import sort in
the new toggle test file).

## Notable / deferred

- A "soft-disable" middleware that would short-circuit incoming
  traffic on bind-only adapters (WebhookAdapter, SlackAdapter)
  was considered and dropped per the Phase 27 context decision
  3. The honest 400 with a clear message and a disabled n/a
  button in the dashboard is the v0.3 contract; the upstream
  adapters where disable actually matters are the lifecycle
  ones (Discord, Email)
- The Phase 26 deferred wiring landed here and is verified by
  two new tests: `test_app_state_tool_registry_is_a_registry`
  proves the field is wired, and
  `test_tool_providing_adapter_registers_tool_on_app_state`
  proves the round trip through `AdapterContext.tool_registry`
  works
- Toggle state is not persisted across server restarts. A
  restart re-runs discovery and re-binds adapters fresh. v0.4
  may add an opt-in persistence flag for operators who want a
  permanently disabled adapter
- `/api/chat` and `/api/chat/stream` continue to build their own
  per-request `ToolRegistry` from `_build_default_registry`.
  Merging the adapter-provided tools into the chat path is a
  v0.4 concern because it intersects with per-profile
  `allowed_tools` filtering, which is out of scope for Phase 27
- No auth on the toggle routes. Same local-only posture as
  Phase 22. Production lockdown for v0.4
- The toggle button does not block during the in-flight POST.
  The follow-up `loadAdapters()` reflects the final state. A
  spinner could be a v0.4 polish if operators ever complain
