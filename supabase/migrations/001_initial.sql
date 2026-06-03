-- Supabase Postgres migration: initial schema for horus-os Supabase sync (Phase 65).
--
-- Apply this file once against your Supabase project using the Supabase SQL editor
-- (with the service role / "Connect" -> SQL Editor) or via psql:
--
--   psql "$DATABASE_URL" -f supabase/migrations/001_initial.sql
--
-- No Supabase CLI is required. The service role has BYPASSRLS by default so the
-- sync adapter can write freely. Anon and authenticated roles are deny-all except
-- for the explicit SELECT policy added for the dashboard read path (SUPA-04).
--
-- Tables mirrored from local SQLite (SYNC_TABLES from supabase_adapter.py):
--   traces, agent_profiles, tasks, sync_health

-- ---------------------------------------------------------------------------
-- traces
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS traces (
    trace_id              TEXT PRIMARY KEY,
    created_at            TEXT NOT NULL,
    provider              TEXT NOT NULL,
    model                 TEXT NOT NULL,
    prompt                TEXT NOT NULL,
    response_text         TEXT NOT NULL DEFAULT '',
    tool_uses             TEXT NOT NULL DEFAULT '[]',
    usage                 TEXT NOT NULL DEFAULT '{}',
    latency_ms            INTEGER,
    status                TEXT NOT NULL DEFAULT 'success',
    error_message         TEXT,
    parent_trace_id       TEXT,
    agent_profile_name    TEXT,
    total_input_tokens    INTEGER,
    total_output_tokens   INTEGER,
    total_cost_usd        DOUBLE PRECISION,
    total_duration_ms     INTEGER
);

ALTER TABLE traces ENABLE ROW LEVEL SECURITY;

-- service_role bypasses RLS by default in Supabase (BYPASSRLS privilege).
-- Deny all access to anon and authenticated roles:
CREATE POLICY "service_role_only" ON traces
    FOR ALL TO anon, authenticated USING (false);

-- SUPA-04: allow anon SELECT so the Vercel-deployed dashboard can read traces
-- with the public anon key (RLS still enforced for writes):
CREATE POLICY "anon_select" ON traces
    FOR SELECT TO anon USING (true);

-- ---------------------------------------------------------------------------
-- agent_profiles
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_profiles (
    name          TEXT PRIMARY KEY,
    system_prompt TEXT NOT NULL DEFAULT '',
    default_model TEXT,
    allowed_tools TEXT,
    memory_scope  TEXT,
    color         TEXT,
    description   TEXT,
    soul_path     TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

ALTER TABLE agent_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_only" ON agent_profiles
    FOR ALL TO anon, authenticated USING (false);

CREATE POLICY "anon_select" ON agent_profiles
    FOR SELECT TO anon USING (true);

-- ---------------------------------------------------------------------------
-- tasks
-- ---------------------------------------------------------------------------

-- Mirrors the local SQLite tasks table (minus the local autoincrement id),
-- exactly as traces and agent_profiles do. The sync adapter strips the local
-- surrogate id before POSTing, so the remote table keys on task_id.
CREATE TABLE IF NOT EXISTS tasks (
    task_id            TEXT PRIMARY KEY,
    title              TEXT NOT NULL,
    description        TEXT NOT NULL DEFAULT '',
    status             TEXT NOT NULL DEFAULT 'pending',
    agent_profile_name TEXT,
    trace_id           TEXT,
    is_demo_seed       INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_only" ON tasks
    FOR ALL TO anon, authenticated USING (false);

CREATE POLICY "anon_select" ON tasks
    FOR SELECT TO anon USING (true);

-- ---------------------------------------------------------------------------
-- sync_health
-- ---------------------------------------------------------------------------
-- Denormalized last-sync record pushed by the sync adapter each cycle.
-- Keyed by a single text id (e.g. 'default') so the adapter can upsert it
-- in one call without accumulating rows.

CREATE TABLE IF NOT EXISTS sync_health (
    id             TEXT PRIMARY KEY,
    last_synced_at TEXT NOT NULL,
    synced_tables  TEXT NOT NULL DEFAULT '[]'
);

ALTER TABLE sync_health ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_only" ON sync_health
    FOR ALL TO anon, authenticated USING (false);

CREATE POLICY "anon_select" ON sync_health
    FOR SELECT TO anon USING (true);

-- ---------------------------------------------------------------------------
-- check_rls_status() RPC helper
-- ---------------------------------------------------------------------------
-- Called by `horus-os doctor --supabase` via POST /rest/v1/rpc/check_rls_status.
-- Returns one row per table in the public schema with its RLS flag and policy count.
-- SECURITY DEFINER runs with the function owner's privileges (service_role) so it
-- can query pg_class and pg_policy catalog tables even when called by anon.

CREATE OR REPLACE FUNCTION check_rls_status()
RETURNS TABLE(table_name text, rls_enabled boolean, policy_count bigint)
LANGUAGE sql
SECURITY DEFINER
AS $$
    SELECT
        c.relname::text,
        c.relrowsecurity,
        COUNT(p.polname)
    FROM pg_class c
    LEFT JOIN pg_policy p ON p.polrelid = c.oid
    WHERE c.relkind = 'r'
      AND c.relnamespace = 'public'::regnamespace
    GROUP BY c.relname, c.relrowsecurity
    ORDER BY c.relname;
$$;
