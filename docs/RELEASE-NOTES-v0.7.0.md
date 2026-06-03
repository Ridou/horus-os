# v0.7.0 - Command Center

> This file is the DRAFTED GitHub Release body for v0.7.0. It is staged in the
> repository, not published. The tag push, GitHub Release publish, and merge to
> main are owner-confirmed final actions; see the footer.

The Command Center milestone. v0.7.0 turns horus-os from a single-page
vanilla-JS dashboard into a polished Next.js command center with a design
system, a Setup-and-Verify integrations surface, an opt-in Discord control bot,
an opt-in Supabase sync loop, a cron scheduler with an always-on service, and an
opt-in Vercel deploy path. v0.6 (Contribution Gate) was never tagged, so 0.7.0
follows 0.5.0 directly in the tag history.

This release adds no removals and no deprecations. Every v0.5 surface keeps
working byte-identical, `pip install horus-os` (no extras) still starts and runs
the local runtime fully, and the SQLite schema upgrade is additive and
idempotent.

## Upgrade notes

See [docs/MIGRATION-v0.5-to-v0.7.md](MIGRATION-v0.5-to-v0.7.md) for the complete
upgrade guide from v0.5: the additive v6 to v12 schema migration, the new
optional extras, the new environment variables, the new CLI surfaces, and the
prominent no-auth / open-CORS exposure caveat for any non-localhost deployment.

## What is new

- **Design system and layout shell (Phase 60).** A Tailwind v4 token source,
  Radix-backed `Modal` and `Stepper` primitives, a four-state pulsing
  `StatusDot`, and an `AppShell` with a locked ten-item sidebar (Home, Team,
  Memory, Tasks, Activity, Traces, Costs, Integrations, Settings, About).
- **Integrations surface and read-only API (Phase 61).** A ten-card
  Integrations page with per-integration walkthroughs (Modal plus Stepper,
  read-only in demo mode), a readiness summary, and a read-only
  `GET /api/integrations` route that never echoes secret values.
- **Key-write endpoint and verification engine (Phase 62).** A loopback-guarded
  `POST /api/integrations/{name}/keys` plus a `POST /verify` probe that never
  echoes the key value, refuses in demo mode (403), writes `.env` with
  `chmod 600`, and invalidates a saved verification when the key hash changes.
- **Tier-1 dashboard pages, starter team, and seed content (Phase 63).** A
  `/tasks` page and a full-page `/team/[slug]` agent detail route,
  `GET /api/tasks` plus task and trace delete routes, a guided tour, and
  idempotent seed content (a starter team and demo tasks).
- **Discord control bot (Phase 64).** The `[discord]` adapter becomes a control
  bot: create-only, non-destructive channel bootstrap, deny-by-default admin
  gating, slash commands, and a `#horus` thread-dispatch flow.
- **Supabase sync loop and schema migrations (Phase 65).** An opt-in
  `[supabase]` background sync loop that pushes traces, agent profiles, and
  tasks, with cursors stored locally so the runtime survives Supabase downtime.
  The service key never reaches a browser-accessible route or a `NEXT_PUBLIC_*`
  value, every synced table ships Row Level Security, and a
  `horus-os doctor --supabase` command reports per-table RLS state without
  printing the key.
- **Cron scheduler and always-on service (Phase 66).** A scheduler
  (core-on-by-default, opt-out via `HORUS_OS_DISABLE_SCHEDULER`) that fires agent
  profiles on cron schedules, a `horus-os schedule` subcommand family, a
  cross-platform `horus-os service` install path (systemd, launchd, NSSM) with
  `horus-os doctor --service`, and a `docs/REMOTE.md` remote-access guide.
- **Vercel deploy path, GitHub tool, and configurable API base (Phase 67).** A
  `NEXT_PUBLIC_API_BASE` abstraction so the static export can point at a remote
  API origin, an opt-in `[vercel]` deploy path, and an opt-in read-only
  `github_read` agent tool behind the `[github]` extra that never echoes
  `GITHUB_TOKEN`.

## Schema change (v6 to v12, additive and idempotent)

v0.5 ships schema version 6, so a v0.5 database advances to v12 on first v0.7
startup. The v0.7 phases add five tables across the milestone:
`integration_verification_state` (Phase 62), `tasks` (Phase 63),
`discord_feedback` (Phase 64), `sync_cursors` (Phase 65), and `schedules`
(Phase 66), plus three nullable `agent_profiles` columns for the starter team.
Every migration is additive and idempotent, runs automatically on first
startup, and leaves pre-v0.7 rows byte-identical. The `schema_version` table
reports `12` once the migration completes; the migration note documents how to
query it.

## Optional extras

`pip install horus-os` (no extras) installs none of the optional extras and
still runs the full local runtime. The package ships ten optional extras:

| Extra | What it adds |
|-------|--------------|
| `anthropic` | Anthropic Claude provider SDK. |
| `gemini` | Google Gemini provider SDK. |
| `dashboard` | FastAPI and uvicorn web dashboard server. |
| `discord` | Discord control bot and adapter. |
| `supabase` | Cloud SQLite mirror sync. |
| `slack` | Slack adapter. |
| `calendar` | Google Calendar adapter. |
| `otel` | OpenTelemetry exporter. |
| `vercel` | Observe-only Vercel deploy client. |
| `github` | Read-only GitHub repository tool. |

`pip install 'horus-os[all]'` installs the AI providers (`anthropic`, `gemini`),
the `dashboard`, `slack`, `calendar`, and `otel` extras. It deliberately
EXCLUDES the four opt-in integrations: `[discord]`, `[supabase]`, `[vercel]`,
and `[github]`. Install those individually when you want them, for example:

```
pip install 'horus-os[discord]'
pip install 'horus-os[supabase]'
pip install 'horus-os[vercel]'
pip install 'horus-os[github]'
```

You can combine extras, for example `pip install 'horus-os[supabase,github]'`.
An install-smoke test pins this `[all]`-exclusion invariant so neither
`pip install horus-os` nor `pip install 'horus-os[all]'` pulls any of the four
opt-in integrations.

## New environment variables

All of the following are optional. The local runtime starts with none of them
set; each lights up only the integration it belongs to. Use placeholder values
like `your-api-key` and never commit a real secret.

`HORUS_OS_DISCORD_TOKEN`, `HORUS_OS_DISCORD_GUILD_ID`,
`HORUS_OS_DISCORD_ADMIN_ROLE_ID`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`,
`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
`HORUS_OS_VERCEL_TOKEN`, `GITHUB_TOKEN`, `HORUS_OS_DISABLE_SCHEDULER`,
`HORUS_TZ`, and `NEXT_PUBLIC_API_BASE`.

## Security note: the local API has no authentication layer

The local `/api` ships NO authentication layer and CORS is open. The Phase 62
key-write endpoint is loopback-guarded, but that is a guard on one endpoint, not
a dashboard-wide auth layer. Binding the server to a routable interface
(`--host 0.0.0.0`), or pointing `NEXT_PUBLIC_API_BASE` at a public origin,
exposes an unauthenticated dashboard and API to anyone who can reach it. Adding
an authentication layer is a prerequisite before ANY non-localhost exposure.
Until then, keep the runtime on loopback or put it behind a network-level auth
boundary such as a Tailscale tailnet (see `docs/REMOTE.md`).

## Release actions pending owner confirmation

This release body is DRAFTED and staged in the repository. It has not been
published. The following final release actions are NOT yet performed and await
explicit owner go-ahead:

- The three-OS hard gate (macOS + Ubuntu + Windows by Python 3.11 + 3.12 with
  all extras) is confirmed by GitHub Actions CI, which requires a push. That
  cross-OS green is a post-push CI step the owner triggers.
- `git push` of the release commits to the remote.
- The annotated tag push (`git push origin v0.7.0`).
- The GitHub Release publish (`gh release create v0.7.0 --notes-file
  docs/RELEASE-NOTES-v0.7.0.md ...`).
- Any merge to `main`.

The owner performs these steps after confirming CI is green; no automated step
in this phase crosses that boundary.
