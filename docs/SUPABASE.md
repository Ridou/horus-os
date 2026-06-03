# Supabase integration guide

horus-os can optionally push local SQLite data to a Supabase project so a
Vercel-deployed dashboard can display live data. The integration is
**completely optional**: the local runtime starts and runs with zero Supabase
configuration. The sync loop only activates when the server-side env vars are
present.

## Prerequisites

Install the `[supabase]` optional extra (adds `httpx` as a runtime dep):

```bash
pip install 'horus-os[supabase]'
```

## Required env vars

Set these on the machine running `horus-os serve`:

```bash
export SUPABASE_URL=https://your-project.supabase.co
export SUPABASE_SERVICE_KEY=your-service-role-key
```

**IMPORTANT - two-key model:**

| Env var | Where it lives | Purpose |
|---------|---------------|---------|
| `SUPABASE_SERVICE_KEY` | Server only (never in browser) | Sync loop writes; bypasses RLS |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Browser / Vercel build env | Dashboard reads; RLS enforced |

**`SUPABASE_SERVICE_KEY` is a secret and must NEVER be set as a `NEXT_PUBLIC_*`
variable.** The service role key bypasses row-level security; if it reached
the browser bundle, any visitor could read and write all your data.

Only `NEXT_PUBLIC_SUPABASE_ANON_KEY` is safe to expose via Vercel's build
environment or any other browser-facing surface (SUPA-02 / TEST-29).

## Apply the Postgres migration

The `supabase/migrations/001_initial.sql` file creates the mirrored tables
(`traces`, `agent_profiles`, `tasks`, `sync_health`) with row-level security
and the `check_rls_status()` RPC helper.

Apply it once in the Supabase SQL editor (Project Settings -> SQL Editor) or
via psql with the service role connection string:

```bash
psql "$DATABASE_URL" -f supabase/migrations/001_initial.sql
```

No Supabase CLI is required. The migration is idempotent (`CREATE TABLE IF
NOT EXISTS`, `CREATE OR REPLACE FUNCTION`).

### What the migration creates

- Four tables: `traces`, `agent_profiles`, `tasks`, `sync_health`
- `ENABLE ROW LEVEL SECURITY` on every table
- A `service_role_only` deny-all policy (anon/authenticated cannot read or write)
- An `anon_select` permissive SELECT policy so the dashboard anon key can read
- The `check_rls_status()` SQL function callable via PostgREST RPC

## Verifying the integration

Run the doctor subcommand with the server-only env vars set:

```bash
SUPABASE_URL=https://your-project.supabase.co \
SUPABASE_SERVICE_KEY=your-service-role-key \
horus-os doctor --supabase
```

Expected output (all tables should show `RLS=on`):

```
traces: RLS=on policies=2
agent_profiles: RLS=on policies=2
tasks: RLS=on policies=2
sync_health: RLS=on policies=2
```

If any table shows `RLS=OFF`, reapply the migration SQL and check that the
`ALTER TABLE ... ENABLE ROW LEVEL SECURITY` statements ran successfully.

## How the sync loop works

When `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are present, `horus-os serve`
starts a background asyncio task that:

1. Reads per-table cursors from a local `sync_cursors` SQLite table (not from
   Supabase, so the cursor survives Supabase downtime).
2. Queries each table for rows newer than the stored cursor.
3. POSTs the new rows to `https://your-project.supabase.co/rest/v1/{table}`
   using `Prefer: resolution=merge-duplicates` (upsert by primary key).
4. Advances the local cursor and pushes a `sync_health` row to Supabase.

The sync runs every 30 seconds. It is push-only (local SQLite is the source of
truth). Supabase downtime degrades gracefully: the adapter logs an error and
retries on the next tick.

## Dashboard read path (SUPA-04)

When deployed to Vercel, set these build env vars (server-safe key excluded):

```bash
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

The dashboard will read traces, agent profiles, and tasks directly from
Supabase using the anon key. Row-level security ensures the anon key can only
SELECT (the `anon_select` policy), never INSERT, UPDATE, or DELETE.

### Security tradeoff: anon SELECT makes synced content world-readable

The `anon_select` policy is `USING (true)`, which grants an unconditional read
of every row to anyone holding the public anon key. The anon key is published
in the browser bundle (`NEXT_PUBLIC_SUPABASE_ANON_KEY`), so anyone who can load
the dashboard, or who simply has the anon key, can read:

- every `traces` row, including full prompts and response text,
- every `agent_profiles` row, including every `system_prompt`,
- every `tasks` row, including task titles and descriptions.

In short, all synced prompt, response, and task text becomes publicly readable
to any holder of the anon key. Prompts and system prompts frequently carry
sensitive context, so treat anything you sync as public.

This is the intended SUPA-04 design for a single trusted operator. If your
deployment is not a single trusted operator, scope the `anon_select` policy or
move reads behind Supabase Auth (`TO authenticated`) before exposing the
dashboard, and only sync data you are comfortable making world-readable.

## Security checklist

- [ ] `SUPABASE_SERVICE_KEY` is set only on the server, never in Vercel's
      NEXT_PUBLIC_* build env
- [ ] `NEXT_PUBLIC_SUPABASE_ANON_KEY` is set in Vercel build env (anon key only)
- [ ] `horus-os doctor --supabase` shows `RLS=on` for all tables
- [ ] `pytest tests/test_supabase_secret_safety.py` passes (no NEXT_PUBLIC_
      violations in env or built bundle)
- [ ] You accept that `anon_select USING (true)` makes all synced prompts,
      responses, system prompts, and task text readable by any holder of the
      public anon key (scope the policy or use Supabase Auth if this is not a
      single trusted operator)
