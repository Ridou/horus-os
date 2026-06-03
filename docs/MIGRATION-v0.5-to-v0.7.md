# Migration from v0.5 to v0.7

## TL;DR

The upgrade path is v0.5 to v0.7 because v0.6 (Contribution Gate) was
never tagged, so v0.7.0 follows v0.5.0 directly. v0.7 is purely
additive. Every v0.5 surface keeps working byte-identical: no
removals, no deprecations, no breaking changes. `pip install horus-os`
(no extras) still starts and runs the local runtime fully.

There are no manual migration steps. The SQLite schema upgrade is
additive and idempotent and runs automatically on first v0.7 startup.

What lights up: a polished Next.js command center with a design system
and layout shell, a Setup-and-Verify integrations surface with a
read-only API and a loopback-guarded key-write endpoint, tier-1
dashboard pages with a starter team and seed content, an opt-in
Discord control bot, an opt-in Supabase sync loop, a cron scheduler
with an always-on cross-platform service, and an opt-in Vercel deploy
path with a configurable API base and a read-only GitHub tool.

## What is new

### Design system and layout shell (Phase 60)

A Tailwind v4 token source, Radix-backed `Modal` and `Stepper`
primitives, a four-state pulsing `StatusDot`, and an `AppShell` with a
locked ten-item sidebar. The CI em-dash and reserved-private-name
guards land here, scoped to the changed-file diff.

### Integrations surface and read-only API (Phase 61)

A ten-card Integrations page with per-integration walkthroughs, a
readiness summary, and a read-only `GET /api/integrations` route that
never echoes secret values.

### Key-write endpoint and verification engine (Phase 62)

A loopback-guarded `POST /api/integrations/{name}/keys` plus a
`POST /verify` probe. The endpoint never echoes the key value, refuses
in demo mode with a 403, writes `.env` with `chmod 600`, and
invalidates a saved verification when the key hash changes.

### Tier-1 dashboard pages, starter team, and seed content (Phase 63)

A `/tasks` page and a full-page `/team/[slug]` agent detail route,
`GET /api/tasks` plus task and trace delete routes, a guided tour, and
idempotent seed content (a starter team and demo tasks).

### Discord control bot (Phase 64)

The `[discord]` adapter becomes a control bot with create-only,
non-destructive channel bootstrap, deny-by-default admin gating, slash
commands, and a `#horus` thread-dispatch flow.

### Supabase sync loop and schema migrations (Phase 65)

An opt-in `[supabase]` background sync loop that pushes traces, agent
profiles, and tasks, with cursors stored locally so the runtime
survives Supabase downtime. The service key never reaches a
browser-accessible route or a `NEXT_PUBLIC_*` value, every synced
table ships Row Level Security, and an anon-key read path lets the
dashboard read from Supabase when configured and fall back to the
local API otherwise.

### Cron scheduler and always-on service (Phase 66)

A scheduler (core-on-by-default, opt-out via
`HORUS_OS_DISABLE_SCHEDULER`) that fires agent profiles on cron
schedules, a `horus-os schedule` subcommand family, a cross-platform
`horus-os service` install path, and a `docs/REMOTE.md` remote-access
guide.

### Vercel deploy path, GitHub tool, and configurable API base (Phase 67)

A `NEXT_PUBLIC_API_BASE` abstraction so the static export can point at
a remote API origin, an opt-in `[vercel]` deploy path, and an opt-in
read-only `github_read` agent tool behind the `[github]` extra that
never echoes `GITHUB_TOKEN`.

## Schema migration v6 to v12

v0.5 databases (schema version 6) upgrade cleanly on first v0.7
startup. The migration is additive and idempotent, and there are no
manual steps.

Five new tables land across the v0.7 phases:

- `integration_verification_state` (Phase 62) - records the last
  verification outcome per integration, keyed to the current key hash
  so a key change invalidates a stale "verified" status.
- `tasks` (Phase 63) - one row per task with a five-value status, used
  by the `/tasks` page and the `GET /api/tasks` route.
- `discord_feedback` (Phase 64) - one row per Discord reaction on a
  control-bot message, recording the emoji and whether it was positive.
- `sync_cursors` (Phase 65) - one row per synced table tracking the
  local high-water mark for the Supabase push loop. Stored locally so
  sync resumes correctly after Supabase downtime.
- `schedules` (Phase 66) - one row per cron schedule with the
  canonical cron expression, the target agent profile, the prompt, the
  catch-up policy, and the run-state columns.

The v6 to v7 step also adds three nullable columns to the existing
`agent_profiles` table (`color`, `description`, `soul_path`) that back
the v0.7 starter team; existing rows keep these columns NULL. Every
change is additive: pre-v0.7 rows read back byte-identical, the new
tables start empty, and no existing column changes type.

## New optional extras

Four opt-in integration extras join the package. Each is installed
explicitly and all four are EXCLUDED from `[all]`, so neither
`pip install horus-os` nor `pip install 'horus-os[all]'` pulls any of
them. An install-smoke test pins this exclusion invariant.

- `[discord]` - the Discord control bot adapter.
  Install: `pip install 'horus-os[discord]'`
- `[supabase]` - the Supabase sync loop and doctor command.
  Install: `pip install 'horus-os[supabase]'`
- `[vercel]` - the Vercel deploy path.
  Install: `pip install 'horus-os[vercel]'`
- `[github]` - the read-only GitHub tool.
  Install: `pip install 'horus-os[github]'`

You can combine extras, for example
`pip install 'horus-os[supabase,github]'`. The local runtime starts
and runs fully with none of them installed.

## New environment variables

All of the following are optional. The local runtime starts with none
of them set; each lights up only the integration it belongs to. Use
placeholder values like `your-api-key` and `your-project` and never
commit a real secret.

- `HORUS_OS_DISCORD_TOKEN` - the Discord bot token.
- `HORUS_OS_DISCORD_GUILD_ID` - the target guild (server) id.
- `HORUS_OS_DISCORD_ADMIN_ROLE_ID` - the role id allowed to run admin
  commands (deny-by-default when unset).
- `SUPABASE_URL` - the Supabase project URL (server-side).
- `SUPABASE_SERVICE_KEY` - the Supabase service-role key. Server-side
  only. Never expose this through a `NEXT_PUBLIC_*` variable or a
  browser-reachable route.
- `NEXT_PUBLIC_SUPABASE_URL` - the Supabase project URL for the
  browser read path.
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` - the Supabase anon (public) key for
  the browser read path. Row Level Security is the boundary, not this
  key.
- `HORUS_OS_VERCEL_TOKEN` - the Vercel deploy token.
- `GITHUB_TOKEN` - the token for the read-only `github_read` tool.
  Unset still works for public reads at the unauthenticated rate.
- `HORUS_OS_DISABLE_SCHEDULER` - set to `true` to make the scheduler a
  silent no-op (opt-out escape hatch).
- `HORUS_TZ` - override the scheduler timezone. Defaults to the OS
  local timezone, resolved with no network call.
- `NEXT_PUBLIC_API_BASE` - the API origin the static export targets.
  Unset means same-origin `/api`; set means a remote-origin `/api`.

## New CLI surfaces

- `horus-os schedule` - create, list, edit, delete, enable, and
  disable cron schedules. Schedules are stored in the canonical cron
  form.
- `horus-os service` - install, uninstall, start, stop, and check an
  always-on service (systemd on Linux, launchd on macOS, NSSM on
  Windows). `horus-os service install --print` emits the service
  definition without touching the system.
- `horus-os doctor --service` - report whether the always-on service
  is registered and running.
- `horus-os doctor --supabase` - report per-table Row Level Security
  state. The service key value is never printed.

## Warning: the local API has no authentication layer

> The local `/api` ships NO authentication layer and CORS is open. The
> Phase 62 key-write endpoint is loopback-guarded, but that is a guard
> on one endpoint, not a dashboard-wide auth layer. Binding the server
> to a routable interface (`--host 0.0.0.0`), or pointing
> `NEXT_PUBLIC_API_BASE` at a public origin, exposes an
> unauthenticated dashboard and API to anyone who can reach it.
>
> Adding an authentication layer is a prerequisite before ANY
> non-localhost exposure. Until then, keep the runtime on loopback, or
> put it behind a network-level auth boundary such as a Tailscale
> tailnet (see `docs/REMOTE.md`). Do not expose the dashboard on the
> public internet.

## Breaking change scan

There are no breaking changes to v0.5 features. Every public API,
every persisted schema column, every CLI flag, every dashboard tab,
and every adapter contract from v0.5 continues to work byte-identical
under v0.7. v0.7 is purely additive over v0.5.

## Verification

The migration ran successfully when the `schema_version` table reports
`12`. Query it with the `sqlite3` CLI, pointing at the `horus.sqlite`
database under your platform's data directory:

```
# macOS
sqlite3 "$HOME/Library/Application Support/horus-os/horus.sqlite" "SELECT version FROM schema_version"
# Linux
sqlite3 "$HOME/.local/share/horus-os/horus.sqlite" "SELECT version FROM schema_version"
# Windows (PowerShell)
sqlite3 "$env:APPDATA\horus-os\horus.sqlite" "SELECT version FROM schema_version"
```

If you set `HORUS_OS_DATA_DIR`, the database is `horus.sqlite` inside
that directory instead.

Expected output: `12` (the schema version current at v0.7). Later
releases bump this number as they add additive tables, so a value
above `12` is also healthy. If the value is below `12`, the v0.7
runtime did not finish its startup migration. Check the server logs
for the migration error and re-run `horus-os serve`.

## See also

- `CHANGELOG.md` `[0.7.0]` section: the complete v0.7 change log.
- `docs/REMOTE.md`: remote-access and always-on service guide,
  including the Tailscale tailnet auth boundary and the funnel
  do-not warning.
- `docs/SUPABASE.md`: the Supabase two-key model and the
  `horus-os doctor --supabase` Row Level Security check.
- `README.md` "Optional extras" section: the full opt-in extra list
  and which extras `[all]` includes versus excludes.
