# Phase 30 Plan 01 Summary

**Status:** Shipped pending CI confirmation
**Date:** 2026-05-24
**Requirements:** TEST-07, TEST-08, TEST-09, TEST-10

## What shipped

`scripts/install_smoke.py` grew from 18 checks to 20 checks; the v0.1
and v0.2 surfaces still run verbatim and the v0.3 surface is now
covered. `tests/test_install_smoke.py` gained two new marker
assertions so the v0.3 checks also ride the regular lint+test pytest
matrix. The CI workflow needed no changes; the `install-smoke` job
still runs `python scripts/install_smoke.py` with no arguments.

## Files

| File | Change | Why |
|------|--------|-----|
| `scripts/install_smoke.py` | +85 / -5 | Public-surface imports extended with LifecycleAdapter + AdapterRegistry + AdapterEntry + four bundled adapter classes; new per-module direct-import smoke; new TestClient subprocess that hits GET /api/adapters and asserts the six-key shape plus a POST /api/adapters/<bogus>/disable 404 check; `run_python()` learned an optional `extra_args` parameter so the TestClient snippet can take the smoke tmp_dir as `argv[1]` |
| `tests/test_install_smoke.py` | +4 / -0 | Assert on the two new v0.3 marker substrings |
| `.github/workflows/ci.yml` | unchanged | The script keeps the same no-args invocation; `.[all]` already pulls in FastAPI via the `dashboard` extra |

## Smoke script check list (post-Phase 30)

v0.1 surface (Phase 10): unchanged, checks 1-5.
v0.2 surface (Phase 20): unchanged, checks 6-13 (schema_version,
traces columns, agent_profiles bootstrap, agents list, agents CRUD
round-trip, traces empty, run without keys streaming + buffered,
serve --help, public-surface imports + discover_adapters()).

v0.3 surface (Phase 30) added:

14. Each bundled adapter module imports directly (lazy SDK pattern).
    A subprocess imports `DiscordAdapter`, `SlackAdapter`,
    `EmailAdapter`, `CalendarAdapter`, `WebhookAdapter` via their
    fully-qualified module paths.
15. `GET /api/adapters` via TestClient returns 200 with the
    `{"adapters": [...]}` body shape; every entry carries the six
    Phase 27 keys (`name`, `status`, `last_activity_at`,
    `error_count`, `error_message`, `supports_toggle`).
16. `POST /api/adapters/does_not_exist_xyz/disable` returns 404 so
    the toggle route is confirmed mounted end-to-end without
    needing real adapter tokens.

The public-surface import smoke (check 13) also grew: it now imports
`LifecycleAdapter`, `AdapterRegistry`, `AdapterEntry` from the
top-level `horus_os` package and `DiscordAdapter`, `SlackAdapter`,
`EmailAdapter`, `CalendarAdapter`, `WebhookAdapter` from
`horus_os.adapters`. The same subprocess asserts
`len(discover_adapters()) >= 1`.

## Test count delta

| Suite | Before | After |
|-------|--------|-------|
| install_smoke wrapper | 1 | 1 (same test, added assertions) |
| full suite | 447 | 447 |

## Verification

- `python scripts/install_smoke.py` exits 0 locally with all 20 OK lines
- `python -m pytest -q` reports 447 passed in ~5s
- `ruff check .` clean
- `ruff format --check .` clean
- No production code under `src/` changed
- No em-dashes / en-dashes in new files
- Commits land in three atoms: docs (plan+context), feat (smoke
  script + wrapper), docs (this summary)

## Notable design choices

- The TestClient pass runs in a subprocess via `run_python()` rather
  than in-process so FastAPI loads in the child only. FastAPI is an
  optional dependency; keeping the smoke driver itself stdlib-only
  matches the Phase 20 design.
- The TestClient snippet takes the smoke driver's tmp_dir as
  `argv[1]`. That reuses the already-initialised SQLite database in
  the same tempdir, avoiding a second init round trip.
- The toggle 404 path was picked over actually exercising
  enable/disable against a real adapter. Real lifecycle hooks need
  real tokens (Discord bot token, Slack signing secret, Google
  OAuth refresh token); CI has none of those, so the 404 path is
  what proves the route is mounted. End-to-end toggle behaviour
  against a stubbed lifecycle adapter is already covered in
  `tests/test_server_adapters_toggle.py` (Phase 27 + 29).
- The per-module smoke is a single subprocess that imports all four
  modules at once. If any one imports its SDK at the top level the
  subprocess fails on that line and the smoke output names the
  failing module clearly.
- The public-surface snippet now also imports `WebhookAdapter`
  explicitly so the smoke covers the full set of re-exports from
  `horus_os.adapters.__init__`, not just the new four.

## Notable / deferred

- Live adapter bind paths (Discord gateway connect, Slack signing
  verification, Gmail polling, Calendar polling) are intentionally
  not exercised. Those need tokens. They are unit-tested in Phases
  23-26 with fake SDKs injected via `sys.modules`.
- The four adapter `start` hooks DO fire inside the TestClient
  lifespan, but each one short-circuits when its required env var
  (token, secret, credentials) is missing. The error is captured
  into `AdapterRegistry` per Phase 22 and never aborts startup,
  so the smoke passes even though four of the five adapters end
  up in the `error` state on a fresh CI runner.
- No matrix change. Ubuntu, macOS, Windows by Python 3.11 and 3.12
  stays exactly as Phase 10 + Phase 20 set it.
- Package version stays at 0.2.0. The bump to 0.3.0 and the tag are
  Phase 31 work.
