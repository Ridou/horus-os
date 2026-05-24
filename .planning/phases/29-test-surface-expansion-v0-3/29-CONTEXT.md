# Phase 29 Context: Test surface expansion (v0.3)

**Date:** 2026-05-24
**Phase:** 29
**Status:** Audit complete; gap list below

## Domain

Each v0.3 phase (22 through 27) added tests for its own adapter
surface in isolation. Phase 29 mirrors the Phase 19 pattern: audit
the cross-phase seams between lifecycle hooks, the four new
adapters, the dashboard toggle routes, and the calendar tool
provider; close the gaps no single phase owned. Phase 28 added zero
tests; the suite stands at 437 passing.

## Audit findings

Adapter-internal unit shape is well covered. The seams between the
lifecycle Protocol, `create_app` discover_adapters wiring, the new
toggle routes, and the four concrete adapters are where coverage
thins out.

### Gap A: full lifecycle state-machine arc

`tests/test_adapters_lifecycle.py` covers registry mutators and the
lifespan-driven start and stop hooks in isolation. No test drives
the complete arc `stopped -> running -> mark_error -> error ->
stop -> stopped -> start -> running` through the registry with a
single concrete lifecycle adapter. Phase 22 covered the units;
Phase 29 closes the integration arc.

Will close: add 1 test in `tests/test_e2e_adapter_lifecycle_arc.py`.

### Gap B: toggle cycle with mid-life touch via /api/adapters

`tests/test_server_adapters_toggle.py` confirms disable and enable
flip status and call the hooks, and Phase 22 confirms `touch`
writes a timestamp. No test runs a full disable+enable cycle and
then asserts `touch` from a request path still advances
`last_activity_at` AFTER the re-enable, which is the realistic
operator flow during an outage triage.

Will close: add 1 test in the same file.

### Gap C: four-adapter coexistence via discover_adapters + create_app

`test_e2e_adapter_round_trip.py` covers one fake adapter and the
reference webhook. No test mounts all four new adapters (Discord,
Slack, Email, Calendar) plus the webhook adapter through the live
discover_adapters path and confirms `/api/adapters` lists all
five, `/api/agents` still works, and each adapter's registry
entry has a stable status.

Will close: add 2 tests in `tests/test_e2e_adapters_coexistence.py`.

### Gap D: adapter-error isolation across the four adapters

`test_lifespan_start_exception_isolated` covers a generic broken
adapter. No test puts a real adapter (e.g., Discord with no token)
in the discovered list alongside other real adapters and confirms
the others still bind successfully via `create_app`.

Will close: add 1 test in the coexistence file.

### Gap E: calendar tool E2E via discover_adapters path

Phase 26 covers the Calendar adapter binding tools onto an
explicit `AdapterContext.tool_registry`. Phase 27 covers a stub
`_ToolProvidingAdapter` going through `create_app`. No test
combines the two: the real `CalendarAdapter` discovered via a
stubbed entry point, bound through `create_app`, registers
`list_calendar_events_today` on `app.state.tool_registry`, and
invoking it through that registry returns serialized events.

Will close: add 2 tests in `tests/test_e2e_calendar_tool_wiring.py`.

### Gap F: calendar write-gate E2E via discover_adapters path

`WRITE_ALLOWED=false` keeps `create_calendar_event` off the
registry per Phase 26 unit tests, but no test confirms the
gate still applies after the adapter is mounted via
`create_app`'s lifespan and bind path. This closes the integration
seam between the env gate and the app-level tool registry.

Will close: add 2 tests in the calendar tool wiring file (one
denied at bind, one allowed at bind).

### Gap G: trace path stays clean with multiple adapters bound

`test_e2e_dashboard_composition.py` covers SSE + agents
last_activity_at. No test confirms POST `/api/chat` continues to
produce a trace and surface it through `/api/agents` when the
four new adapters are simultaneously bound, which catches any
inadvertent registry pollution from adapter-side `touch` calls
landing on agent profiles.

Will close: add 1 test in the coexistence file.

## Out of scope for Phase 29

- Re-testing surfaces already covered by phases 22 through 27.
- Wiring `app.state.tool_registry` into `/api/chat`; Phase 27
  deliberately deferred that. Tests stay within the existing
  surface.
- Live Discord, Slack, IMAP, SMTP, or Google API calls.
- Refactoring existing tests for style.
- New production code; Phase 29 only adds tests. If a real bug
  surfaces, surface it in the report rather than patching silently.

## Expected delta

10 new tests minimum across 3 new test files plus 1 new test added
to `tests/test_server_adapters_toggle.py`. Suite target: 437 + at
least 10 = 447 or more. Lint clean. Full suite must stay under 4
seconds.
