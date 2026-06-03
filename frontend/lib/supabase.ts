/**
 * SUPA-04 anon-only Supabase browser client.
 *
 * SECURITY NOTES (SUPA-02, T-65-11):
 * - ONLY the anon key (NEXT_PUBLIC_SUPABASE_ANON_KEY) is used here.
 * - The service key (SUPABASE_SERVICE_KEY) must NEVER be referenced,
 *   imported, or read anywhere in frontend/. This is enforced by TEST-29
 *   (tests/test_supabase_secret_safety.py) at CI time.
 * - Both env vars are NEXT_PUBLIC_* so they are browser-safe.
 *
 * Deploy-time data-source switching via NEXT_PUBLIC_API_BASE is Phase 67
 * and is intentionally absent here.
 *
 * The @supabase/supabase-js import is dynamic so this module is importable
 * and the build/tests pass without the package installed.
 */

/** Minimal local type for a Supabase query chain: select().order().range(). */
export interface SupabaseQuery {
  order(
    column: string,
    opts?: { ascending?: boolean },
  ): SupabaseQuery;
  range(from: number, to: number): Promise<{ data: unknown[] | null; error: { message: string } | null }>;
  select(columns: string): SupabaseQuery;
}

/** Minimal local type for a Supabase browser client. */
export interface SupabaseLike {
  from(table: string): SupabaseQuery;
}

const SUPABASE_URL =
  typeof process !== "undefined"
    ? process.env.NEXT_PUBLIC_SUPABASE_URL
    : undefined;

const SUPABASE_ANON_KEY =
  typeof process !== "undefined"
    ? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
    : undefined;

/**
 * True when both NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY
 * are configured (non-empty). When false, the dashboard falls back to the
 * local /traces path (SUPA-05 escape hatch).
 */
export const isSupabaseConfigured: boolean = Boolean(
  SUPABASE_URL && SUPABASE_ANON_KEY,
);

/**
 * Returns a Supabase browser client when configured, or null otherwise.
 *
 * Returns null (never throws) in three cases:
 * - Either public env var is missing
 * - @supabase/supabase-js is not installed (dynamic import fails)
 * - createClient throws for any reason
 *
 * This ensures the dashboard degrades gracefully to the local data path
 * rather than crashing when Supabase is unavailable or unconfigured (T-65-12).
 *
 * The dynamic import uses a variable specifier so Vite's static analysis does
 * not attempt to resolve @supabase/supabase-js at build time (package is not
 * in package.json; it is an optional runtime dep the user installs only when
 * they want Supabase support). The try/catch handles the missing-package case.
 */
export async function getSupabaseClient(): Promise<SupabaseLike | null> {
  if (!isSupabaseConfigured) {
    return null;
  }
  try {
    // Use indirect specifier so Vite static analysis skips resolution.
    const pkg = "@supabase/supabase-js";
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { createClient } = await (import(/* @vite-ignore */ pkg) as Promise<any>);
    return createClient(SUPABASE_URL!, SUPABASE_ANON_KEY!) as SupabaseLike;
  } catch {
    // Package absent or createClient failed - degrade gracefully.
    return null;
  }
}
