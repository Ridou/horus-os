# Phase 30 Context: Three-OS install verification (v0.3)

**Date:** 2026-05-24
**Phase:** 30
**Status:** Plan staged; install-smoke needs v0.3 surface

## Domain

Phase 10 stood up the `install-smoke` GitHub Actions job. Phase 20
extended it for the v0.2 surface (agents CRUD, schema v4, streaming,
adapter discovery hook). Phases 22-29 then added the v0.3 surface on
top: adapter lifecycle hooks, four bundled adapters (Discord, Slack,
Email, Calendar), a dashboard adapter management tab, status routes,
and toggle routes. The smoke script has not been updated since Phase
20, so a fresh install only confirms that v0.1 and v0.2 still work.

Phase 30 closes the v0.3 gap: same job, same matrix, but the script
exercises the v0.3 surface so a regression on any of three OSes shows
up in CI before release.

## What install_smoke.py already exercises (v0.1 + v0.2)

v0.1 (Phase 10): `--version`, `--help`, `init` happy path, `init`
refuses overwrite without `--force`, `init --force`.

v0.2 (Phase 20): on-disk `schema_version == 4`, `traces` table carries
`parent_trace_id` and `agent_profile_name`, `agent_profiles` is
bootstrapped with the `default` row, `agents list / create / show /
delete` round-trip, `traces` empty-DB marker, `run "hello"` without
keys exits 2 (streaming default branch), `run --agent default
--no-stream "hello"` without keys exits 2 (buffered branch), `serve
--help`, and a `python -c` import smoke for `Adapter`, `AdapterContext`,
`ToolCallEvent`, `discover_adapters`, `run_agent_stream` plus a call
to `discover_adapters()` that returns a list.

## What v0.3 adds and what install-smoke must now verify

The v0.3 surface adds:

- `LifecycleAdapter` Protocol (Phase 22) re-exported from
  `horus_os.adapters` and from the top-level `horus_os` package
- `AdapterRegistry` and `AdapterEntry` (Phase 22) re-exported
- Four bundled adapter classes re-exported from `horus_os.adapters`:
  `DiscordAdapter`, `SlackAdapter`, `EmailAdapter`, `CalendarAdapter`
  (Phases 23-26)
- Four entry-point registrations under `horus_os.adapters` so they
  surface in `discover_adapters()` on a fresh `.[all]` install
- The optional SDKs (`discord.py`, `slack-sdk`,
  `google-api-python-client`, `google-auth-oauthlib`) are pulled in by
  the `.[all]` extra; each adapter module also imports cleanly without
  its SDK installed (lazy-import pattern)
- `GET /api/adapters` status route (Phase 22/27) returning per-adapter
  `name`, `status`, `last_activity_at`, `error_count`, `error_message`,
  `supports_toggle`
- `POST /api/adapters/{name}/enable` and `POST
  /api/adapters/{name}/disable` toggle routes (Phase 27) with 404 for
  unknown adapter names

The smoke script must add coverage for each of those. It runs offline.
GitHub-hosted runners have no API keys, no Discord/Slack tokens, no
Google OAuth credentials, so adapter `start` hooks must never be
invoked end-to-end inside smoke. The shape of the discovery list, the
status route response, and the 404 path for the toggle routes are
what we exercise; live channel bind is covered in Phases 23-26 +
Phase 29 unit and integration tests.

## Out of scope for Phase 30

- Live API calls or provider mocks. CI never has keys or tokens.
- Bumping the package version or tagging a release. That is Phase 31.
- Changing the CI matrix (Ubuntu, macOS, Windows by Python 3.11, 3.12
  stays exactly as Phase 10 set it).
- New runtime dependencies. Stdlib only for new helpers; FastAPI's
  `TestClient` is already available via the `dashboard` extra inside
  `.[all]`.

## Expected delta

`scripts/install_smoke.py` grows by roughly 6 new checks (4 new adapter
class imports as one subprocess smoke, plus `LifecycleAdapter` import,
plus `discover_adapters()` count >= 1, plus `GET /api/adapters` shape,
plus toggle 404 path). The pytest wrapper at `tests/test_install_smoke.py`
needs at most one additional assertion on the v0.3 marker line(s). CI
workflow unchanged; the script's no-args call signature stays. Suite
target: 447 baseline + 0 new (the wrapper already exists). Lint clean.
Three-OS matrix green on push.
