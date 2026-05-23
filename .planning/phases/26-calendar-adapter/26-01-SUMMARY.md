# Phase 26 Plan 01 Summary: Google Calendar adapter

**Date:** 2026-05-24
**Phase:** 26 (Calendar adapter)
**Plan:** 26-01
**Status:** Shipped

## What shipped

`CalendarAdapter`, the first tool-providing v0.3 adapter.
Unlike Discord, Slack, and Email (which ingest external events
into `run_agent`), the Calendar adapter registers agent-callable
tools onto the master tool registry during `bind`. It
implements only the `Adapter` Protocol; no `LifecycleAdapter`,
no background task.

Two tools land:

- `list_calendar_events_today(calendar_id="primary") -> list[dict]`
  Always registered when bind succeeds. Returns events for the
  current UTC day with `summary`, `start`, `end`, `location`,
  `attendees`.
- `create_calendar_event(summary, start_iso, end_iso, calendar_id="primary", description=None) -> dict`
  Gated by `HORUS_OS_CALENDAR_WRITE_ALLOWED == "true"`. The
  flag is checked at bind time (tool not registered when off)
  AND re-checked inside the handler at call time (catches
  operators who flip the flag off mid-run).

`AdapterContext` gained an optional `tool_registry: ToolRegistry | None = None`
field. Default None preserves byte-identical behavior for all
existing callers (Phases 17 through 25). Phase 27 will wire
this through `create_app` so the dashboard auto-exposes
registered adapter tools.

Google libraries (`google-api-python-client`,
`google-auth-oauthlib`) are an optional pip extra and imported
lazily; the module loads cleanly without them. Tests inject
fake `google.*` and `googleapiclient.*` modules into
`sys.modules` to exercise the adapter offline.

OAuth credentials load from `<data_dir>/calendar-token.json`
on bind; expired tokens refresh lazily via
`creds.refresh(Request())`; refresh failures mark the adapter
status `error` without raising.

Tool handlers wrap every API call in `try/except`, returning
`{"error": "..."}` on failure so the agent loop never sees an
uncaught exception. Successful calls bump
`registry.last_activity_at`; failures increment
`registry.error_count`.

## Files touched

- `src/horus_os/adapters/base.py` (modified): added `tool_registry: ToolRegistry | None = None` to `AdapterContext`
- `src/horus_os/adapters/calendar_adapter.py` (new, 313 lines): adapter + tool factories + helpers
- `src/horus_os/adapters/__init__.py` (modified): re-export `CalendarAdapter`
- `pyproject.toml` (modified): `calendar` optional extra, `all` extras update, entry-point declaration
- `tests/test_adapters_calendar.py` (new, 551 lines): 17 offline tests
- `docs/adapters/CALENDAR.md` (new, 207 lines): step-by-step setup guide
- `.planning/phases/26-calendar-adapter/{26-CONTEXT.md,26-01-PLAN.md,26-01-SUMMARY.md}` (new): phase artifacts

## Test count delta

Before: 406 tests passing
After: 423 tests passing (+17)

All ruff lint and format checks pass.

## Commits

1. `docs(26): create phase 26 plan and context`
2. `feat(26): Google Calendar adapter with gated event creation`
3. `test(26): offline tests for the Calendar adapter`
4. `docs(26): Calendar adapter setup guide`
5. `docs(26): summary for plan 26-01` (this commit)

## Deferred / not in scope

- `horus-os calendar auth` CLI command for the OAuth bootstrap;
  operators run the standalone script documented in
  `docs/adapters/CALENDAR.md`. A built-in command is a Phase
  27 / v0.4 polish.
- Multi-calendar listing tool (`list_calendars`). v0.3 ships
  `primary` + arbitrary `calendar_id` parameter.
- Recurring event creation. The create tool does not expose the
  `recurrence` field.
- Local-timezone "today" window. v0.3 uses UTC; the setup
  guide notes the caveat.
- Service account auth. OAuth user flow only.
- Update / delete event tools. Read + create is the v0.3 surface.
- Wiring `AdapterContext.tool_registry` through `create_app`
  so the FastAPI app shares one ToolRegistry across the agent
  and all tool-providing adapters. Phase 27 is the natural
  home: the dashboard view will need this anyway to surface
  adapter-registered tools.

## Verification

- `python -m pytest tests/test_adapters_calendar.py -q` -> 17 passed
- `python -m pytest -q` -> 423 passed
- `ruff check .` -> clean
- `ruff format --check .` -> clean
- `python -c "from horus_os.adapters import CalendarAdapter; CalendarAdapter()"` -> no error
- `google-api-python-client` was NOT installed in the dev env during the test run
