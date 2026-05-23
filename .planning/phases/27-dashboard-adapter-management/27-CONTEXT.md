# Phase 27 Context: Dashboard adapter management

**Date:** 2026-05-24
**Phase:** 27
**Status:** Context captured

## Domain

Phase 27 ships the operator surface for the four v0.3 adapters
(Discord, Slack, Email, Calendar). Phase 22 stood up status
reporting via `GET /api/adapters`. Phase 27 turns that read-only
surface into a control plane: enable and disable toggles, a
dashboard tab that polls live, and per-adapter health rendering.

The dashboard tab is the visible deliverable. The backend
additions are two HTTP routes and one piece of long-deferred
plumbing.

Three pieces ship together:

1. `POST /api/adapters/{name}/disable` and
   `POST /api/adapters/{name}/enable` routes that drive
   `LifecycleAdapter.stop` and `LifecycleAdapter.start` and flip
   the registry status. Adapters without lifecycle hooks return
   400 with a clear reason.
2. The Phase 26 deferred wiring: `create_app` constructs a
   `ToolRegistry`, passes it through `AdapterContext.tool_registry`,
   and exposes it on `app.state.tool_registry` so tool-providing
   adapters (today: Calendar) actually register their tools.
3. An Adapters tab in `static/index.html` that lists adapters with
   status, last activity, error count, error message, and a
   per-adapter toggle button.

## Canonical refs

- `.planning/ROADMAP.md` Phase 27 success criteria
- `.planning/REQUIREMENTS.md` DASH-3-01, DASH-3-02
- `src/horus_os/adapters/base.py` AdapterRegistry, LifecycleAdapter
- `src/horus_os/server/api.py` FastAPI factory, existing
  `GET /api/adapters` route, current bind loop
- `src/horus_os/server/static/index.html` single-page dashboard
- `tests/test_server_adapters.py` Phase 22 patterns
- `tests/test_server_agents.py` Phase 16 patterns
- `tests/test_adapters_lifecycle.py` lifespan and lifecycle dispatch
  patterns with `_FakeEntryPoint` and `_stub_entry_points`
- Phase 22 summary for the registry shape and lifespan story
- Phase 26 context section 2 for the `tool_registry` decision

## Decisions

### 1. Two new routes, no PATCH

`POST /api/adapters/{name}/disable` and
`POST /api/adapters/{name}/enable` are the two new endpoints. We
considered a single PATCH route with a body, but the action
verb is friendlier for both curl and the JS fetch path, and
matches the success-criteria phrasing in the ROADMAP. The
existing `GET /api/adapters` is unchanged in shape.

### 2. Disable means call stop; enable means call start

The behavior is symmetric with the lifespan. `disable` looks the
adapter up by name in the registry, calls `await adapter.stop()`
if the adapter has a `stop` method, and flips the registry entry
to `stopped`. `enable` calls `await adapter.start(context)`
(reusing the same `AdapterContext` instance built at
`create_app`) and flips to `running`. Both use `hasattr` rather
than `isinstance(LifecycleAdapter)` for dispatch, the same
pattern the lifespan uses.

### 3. Non-lifecycle adapters return 400

The reference `WebhookAdapter`, `SlackAdapter` (webhook-shaped),
and `CalendarAdapter` (bind-time tool registration only) have no
`start` or `stop`. Calling `disable` on them returns 400 with
`detail = "adapter {name!r} does not support disable; it has no
stop() hook"`. Same for `enable` when `start` is missing.

A "soft disable" path that just flags the registry as stopped and
short-circuits the route was considered. It was rejected for
v0.3: middleware that consults the registry on every adapter
request would be a new behavior not covered by Phase 22 routes,
and the upstream adapters (Discord socket, Email IMAP poll) are
the ones where disable actually matters. A 400 with a clear
message keeps the contract honest, and the dashboard renders a
disabled button with an explanatory tooltip rather than
pretending it can toggle.

### 4. Adapter not found returns 404

Unknown name returns 404 from both routes. The lookup walks the
discovered adapter list (a small in-memory list) rather than the
registry, because the registry stores only the name and status
and we need the actual adapter object to call its hooks.

### 5. Wire tool_registry through create_app (Phase 26 deferred)

`create_app` constructs an `app_tool_registry = ToolRegistry()`
before building `AdapterContext` and passes it via the new
`tool_registry` kwarg. The registry is also stored on
`app.state.tool_registry` so future routes can read what was
registered. The default-built tools currently constructed inside
`/api/chat` continue to live in a per-request registry; merging
them is a v0.4 concern (the adapter-provided tools are
read-mostly and not yet plumbed into the chat path).

This unblocks the Calendar adapter end-to-end: with this wiring,
a `bind` call that satisfies all env vars and credentials will
register `list_calendar_events_today` onto `app.state.tool_registry`
and we can verify that in tests.

### 6. Status semantics for the toggle

| Before | Action | Hook called | After (success) | After (hook raises) |
|--------|--------|-------------|-----------------|---------------------|
| running | disable | stop | stopped | error |
| stopped | enable | start | running | error |
| error | enable | start | running | error |
| error | disable | stop | stopped | error |

Either toggle from `error` is allowed: the operator may want to
explicitly stop a broken adapter, or try to restart it. The
registry entry already preserves `error_count` and
`error_message`, which keeps the audit trail intact.

### 7. Frontend: new Adapters tab

The dashboard gets a fifth nav button "Adapters" placed after
"Writes". Tab content is a table with columns: name, status,
last_activity_at, error_count, action. Status is rendered as a
color-coded pill: running green (#3fb950, reuse `.pill.success`),
stopped gray (new `.pill.muted`), error red (reuse
`.pill.error`). Action is a button with label "Disable" when
status is running, "Enable" when status is stopped or error,
and a disabled "n/a" button with a tooltip when the adapter has
neither hook. Error message renders as a sub-row below the
error count when present.

The page reads `/api/adapters` on tab activation and polls every
5 seconds while the tab is visible. The poll is a `setInterval`
captured in a module-scoped variable so the existing tab switch
logic can clear it when the user navigates away.

The "neither hook" hint requires the API to surface a
`supports_toggle` field. We add `supports_toggle: bool` to the
`/api/adapters` payload. It is a derived field from
`hasattr(adapter, "start") and hasattr(adapter, "stop")` so the
backend already knows it. This keeps the frontend dumb: no
hardcoded list of "which adapters can toggle".

### 8. No build step

Same as Phase 16. Extend `static/index.html` in place. Vanilla
JS, no framework. The dashboard ships as Python package data.

### 9. Test surface

Two new test files:

- `tests/test_server_adapters_toggle.py`: enable/disable routes.
  404 on unknown name. 400 on adapter without lifecycle hooks.
  Disable on a lifecycle adapter flips status to `stopped` and
  calls `stop`. Enable on a stopped adapter calls `start` and
  flips to `running`. Disable when `stop` raises captures the
  error onto the registry. Enable when `start` raises captures
  the error. A test verifying `app.state.tool_registry` exists
  and is a `ToolRegistry` instance (Phase 26 wiring). A test
  using a fake tool-providing adapter that registers a tool at
  bind time and asserts the tool is visible on
  `app.state.tool_registry`.
- `tests/test_dashboard_adapters.py`: GET `/` returns HTML
  containing `data-tab="adapters"`, `loadAdapters`,
  `toggleAdapter`, the polling interval reference, and the
  status color tokens. No JS execution.

Extend `tests/test_server_adapters.py` to assert
`supports_toggle` is present on every entry and reflects the
hook availability.

### 10. Backwards compatibility

`GET /api/adapters` gains the `supports_toggle` field. Existing
Phase 22 tests assert `set(entry.keys()) == {five fields}`; one
of those assertions changes from five keys to six. Other tests
read fields by name and remain green. The change is documented
in the summary so external dashboards know to expect the
field.

The v0.2 dashboard tabs (Chat, Traces, Agents, Writes) are
untouched. No selector, route, or asset they depend on changes.

## Execution split

Single plan: 27-01. Backend routes + tool_registry wiring,
frontend tab, and tests land together; splitting would create a
state where the frontend points at routes that do not exist or
the tool_registry is wired but no test exercises it.

Atomic commits:

- `docs(27)`: plan + context
- `feat(27)`: enable/disable routes + `tool_registry` wiring in
  `create_app` + `supports_toggle` on `/api/adapters`
- `feat(27)`: Adapters tab in `static/index.html`
- `test(27)`: toggle route tests + dashboard surface tests
- `docs(27)`: phase summary

## Deferred / not in scope

- Restart-on-error retry policies for adapters (operator clicks
  enable manually after fixing the underlying cause).
- Persisting the disabled state across server restarts. v0.3
  treats toggles as in-memory; a restart reads the entry point
  group fresh.
- Soft-disable middleware that gates inbound traffic on
  WebhookAdapter / SlackAdapter (see decision 3).
- Per-adapter log tail in the dashboard. The error_message field
  is the visible signal for now.
- Auth on the toggle routes. Local-only server, same threat
  posture as Phase 22.
- Merging the adapter-provided tool_registry into the chat path's
  default registry. v0.4 concern; `/api/chat` continues to use
  its own per-request registry today.
