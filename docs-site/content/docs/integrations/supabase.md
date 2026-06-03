---
title: "Supabase"
description: "Optionally mirror local SQLite data to a Supabase project so a hosted dashboard can read live traces, agents, and tasks, with row-level security on every table."
---

## Overview

horus-os can push your local SQLite data to a [Supabase](https://supabase.com/) project so a hosted dashboard (for example one deployed to Vercel) can display live data. The integration is completely optional. The local runtime starts and runs with zero Supabase configuration, and the sync loop activates only when the server-side environment variables are present.

The sync is push-only. Your local SQLite database is always the source of truth. Supabase holds a read mirror that a browser-facing dashboard can query.

> [!IMPORTANT]
> Anything you sync to Supabase becomes readable by any holder of the public anon key. This includes full prompts, response text, and agent system prompts. Read [Security tradeoff](#security-tradeoff-synced-content-is-publicly-readable) before you enable sync, and only sync data you are comfortable making world readable.

## Install the extra

The Supabase integration ships in the `supabase` optional extra, which adds `httpx` as a runtime dependency:

```bash
pip install 'horus-os[supabase]'
```

## The two-key model

Supabase issues two keys for a project, and horus-os uses both in different places. Keeping them separated is the most important part of this integration.

| Environment variable | Where it lives | Purpose |
|----------------------|----------------|---------|
| `SUPABASE_SERVICE_KEY` | Server only, never in the browser | The sync loop writes rows. Bypasses row-level security. |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Browser or Vercel build environment | The dashboard reads rows. Row-level security is enforced. |

> [!CAUTION]
> `SUPABASE_SERVICE_KEY` is a secret and must never be set as a `NEXT_PUBLIC_*` variable. The service role key bypasses row-level security. If it reached a browser bundle, any visitor could read and write all of your data.
>
> Only `NEXT_PUBLIC_SUPABASE_ANON_KEY` is safe to expose through Vercel's build environment or any other browser-facing surface.

## Configure server-side environment variables

Set these on the machine that runs `horus-os serve`. These two variables, when both present, are what activate the sync loop:

```bash
export SUPABASE_URL=https://your-project.supabase.co
export SUPABASE_SERVICE_KEY=your-service-role-key
```

If either variable is missing, the sync loop does not start and the rest of horus-os runs normally.

## Apply the Postgres migration

The migration file `supabase/migrations/001_initial.sql` in the repository creates the mirrored tables (`traces`, `agent_profiles`, `tasks`, `sync_health`), enables row-level security, adds the access policies, and defines the `check_rls_status()` RPC helper.

Apply it once. You can paste it into the Supabase SQL editor (Project Settings, then SQL Editor) or run it with `psql` using your service-role connection string:

```bash
psql "$DATABASE_URL" -f supabase/migrations/001_initial.sql
```

No Supabase CLI is required. The migration is idempotent: it uses `CREATE TABLE IF NOT EXISTS` and `CREATE OR REPLACE FUNCTION`, so re-running it is safe.

### What the migration creates

- Four tables: `traces`, `agent_profiles`, `tasks`, and `sync_health`.
- `ENABLE ROW LEVEL SECURITY` on every table.
- A `service_role_only` deny-all policy, so the anon and authenticated roles cannot read or write through normal policies.
- An `anon_select` permissive SELECT policy, so the dashboard anon key can read.
- The `check_rls_status()` SQL function, callable through PostgREST RPC, used by the doctor check below.

## Verify the integration

Run the doctor subcommand with the server-only environment variables set:

```bash
SUPABASE_URL=https://your-project.supabase.co \
SUPABASE_SERVICE_KEY=your-service-role-key \
horus-os doctor --supabase
```

Every table should report `RLS=on`:

```text
traces: RLS=on policies=2
agent_profiles: RLS=on policies=2
tasks: RLS=on policies=2
sync_health: RLS=on policies=2
```

If any table shows `RLS=OFF`, reapply the migration SQL and confirm that the `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` statements ran successfully.

## How the sync loop works

When both `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are present, `horus-os serve` starts a background asyncio task that, on each tick:

1. Reads per-table cursors from a local `sync_cursors` SQLite table. The cursor lives locally, not in Supabase, so it survives Supabase downtime.
2. Queries each table for rows newer than the stored cursor.
3. POSTs the new rows to `https://your-project.supabase.co/rest/v1/{table}` with the header `Prefer: resolution=merge-duplicates`, which upserts by primary key.
4. Advances the local cursor and pushes a `sync_health` row to Supabase.

The loop runs every 30 seconds. It is push-only, so local SQLite stays authoritative. Supabase downtime degrades gracefully: the adapter logs an error and retries on the next tick.

## Dashboard read path

When you deploy the dashboard (for example to Vercel), set these build environment variables. The server-only service key is deliberately excluded:

```bash
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

The dashboard reads traces, agent profiles, and tasks directly from Supabase using the anon key. Row-level security ensures the anon key can only run SELECT (through the `anon_select` policy), never INSERT, UPDATE, or DELETE.

See [Deploy to Vercel](/operations/deploy-to-vercel/) for the full hosting walkthrough.

## Security tradeoff: synced content is publicly readable

The `anon_select` policy uses `USING (true)`, which grants an unconditional read of every row to anyone holding the public anon key. The anon key is published in the browser bundle as `NEXT_PUBLIC_SUPABASE_ANON_KEY`, so anyone who can load the dashboard, or who simply has the anon key, can read:

- every `traces` row, including full prompts and response text,
- every `agent_profiles` row, including every `system_prompt`,
- every `tasks` row, including task titles and descriptions.

In short, all synced prompt, response, and task text becomes publicly readable to any holder of the anon key. Prompts and system prompts frequently carry sensitive context, so treat anything you sync as public.

This is the intended design for a single trusted operator. If your deployment is not a single trusted operator, scope the `anon_select` policy or move reads behind Supabase Auth (`TO authenticated`) before exposing the dashboard, and only sync data you are comfortable making world readable.

## Security checklist

- [ ] `SUPABASE_SERVICE_KEY` is set only on the server, never in Vercel's `NEXT_PUBLIC_*` build environment.
- [ ] `NEXT_PUBLIC_SUPABASE_ANON_KEY` is set in the Vercel build environment (anon key only).
- [ ] `horus-os doctor --supabase` shows `RLS=on` for all tables.
- [ ] You accept that `anon_select USING (true)` makes all synced prompts, responses, system prompts, and task text readable by any holder of the public anon key. Scope the policy or use Supabase Auth if this is not a single trusted operator.

For broader hardening guidance, see [Security](/operations/security/).

## See also

- [Deploy to Vercel](/operations/deploy-to-vercel/)
- [Security](/operations/security/)
- [Integrations overview](/integrations/overview/)
- [Environment variables](/reference/environment-variables/)
