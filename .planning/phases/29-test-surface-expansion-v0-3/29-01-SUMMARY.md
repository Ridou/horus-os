# Phase 29 Plan 01 Summary

**Status:** Shipped
**Date:** 2026-05-24
**Requirements:** TEST-07, TEST-08, TEST-09, TEST-10

## What shipped

Three new test files plus one new test added to the existing
toggle file. 10 net new tests, closing the cross-phase seams no
single phase 22 through 27 plan owned. No production code
changed. Suite went from 437 to 447 passing.

## Files touched

| File | Tests | Gap closed |
|------|-------|------------|
| `tests/test_e2e_adapter_lifecycle_arc.py` | 2 | A: stopped -> running -> error -> stopped -> running arc both through AdapterRegistry alone and through TestClient + disable/enable routes |
| `tests/test_server_adapters_toggle.py` (added 1) | 1 | B: disable then enable then a bound route's touch advances last_activity_at as surfaced via GET /api/adapters |
| `tests/test_e2e_adapters_coexistence.py` | 3 | C: Discord, Slack, Email, Calendar, webhook all listed via /api/adapters with /api/agents still working. D: a Discord error during start does not prevent Calendar or webhook from binding running. G: POST /api/chat trace stays clean while adapters are bound and agent_profile_name does not leak |
| `tests/test_e2e_calendar_tool_wiring.py` | 4 | E: CalendarAdapter via discover_adapters registers list_calendar_events_today on app.state.tool_registry and the tool is invocable through that registry. F: WRITE_ALLOWED gate is honored at the lifespan boundary (allowed path + unset/false denied path) |

## Test count delta

| Surface | Before | After |
|---------|--------|-------|
| e2e_adapter_lifecycle_arc | 0 | 2 |
| server_adapters_toggle | 12 | 13 |
| e2e_adapters_coexistence | 0 | 3 |
| e2e_calendar_tool_wiring | 0 | 4 |
| **full suite** | **437** | **447** |

10 net new tests. `python -m pytest -q` reports 447 passed in
~3.7s, comfortably under the 4s budget.

## Verification

- `python -m pytest -q` reports 447 passed
- `ruff check .` clean (one unused-import fix applied during
  initial coexistence test write, then re-verified)
- `ruff format --check .` reports 89 files already formatted
- grep for unicode dash characters across new tests and the
  phase folder reports zero em-dashes and zero en-dashes
- No production code touched. `git diff main src/` shows zero
  changes

## Commits

1. `docs(29): create phase 29 plan and context`
2. `test(29): full lifecycle state-machine arc through registry and create_app`
3. `test(29): toggle plus touch cycle advances last_activity_at via api adapters`
4. `test(29): calendar tool wiring through create_app discover_adapters`
5. `test(29): four-adapter coexistence and clean traces through create_app`
6. `docs(29): summary for plan 29-01`

## Notable design choices

- The coexistence test exercises Discord and Email through their
  realistic no-env-configured error path rather than fully
  stubbing every SDK. That captures the most common operator
  state (half the integrations configured, half not) and keeps
  the test fast. The error-isolation case is exactly this state.
- The calendar wiring tests reuse the `_install_fake_google`
  shape from `tests/test_adapters_calendar.py` rather than
  importing it directly, so the existing adapter-internal test
  helper stays a pure unit-test fixture and the integration
  tests own their own minimal SDK fakes (smaller surface,
  happy-path only).
- The lifecycle arc test in part 2 drives the disable/enable
  cycle through HTTP routes rather than calling registry
  mutators directly, so it verifies the operator-visible
  contract (status fields in the JSON payload), not just the
  internal state. Part 1 of the same file covers the internal
  state explicitly.
- The chat-trace cleanliness test asserts
  `agent_profile_name is None` on the resulting trace, which
  documents the deliberate semantics: `/api/chat` is the unscoped
  path, and adapters that call `registry.touch(self.name)` from
  their own handlers must not leak into agent profile rows.

## Notable / deferred

- Wiring `app.state.tool_registry` into `/api/chat` so an agent
  can actually invoke `list_calendar_events_today` from a chat
  turn is intentionally deferred (Phase 27 left the wiring as a
  future surface). The calendar wiring tests confirm the tool
  reaches `app.state.tool_registry` and is invocable through
  that registry; the chat-side consumption is out of scope until
  the wiring lands.
- Full Discord and Slack SDK stubs that exercise message routing
  through `create_app` were not added. Each adapter already has
  its own dedicated routing tests against a hand-built bind
  (Phase 23 and Phase 24). The coexistence tests confirm the
  adapters mount cleanly together; the per-adapter routing
  internals are covered by their own phase-23/24 suites.
- A v0.2-to-v0.3 schema-on-disk + dashboard render test was not
  added. Phase 19 already covered the v0.1 on-disk + dashboard
  case, and no schema changes landed in v0.3 that would warrant
  a fresh on-disk test.
