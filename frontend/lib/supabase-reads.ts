/**
 * SUPA-04 real anon read path - one data source: traces.
 *
 * Only the anon key is used (via getSupabaseClient from ./supabase).
 * The service key must never be referenced here or in ./supabase.
 *
 * Deploy-time data-source switching via NEXT_PUBLIC_API_BASE is Phase 67
 * and is intentionally absent here. This module wires the traces read
 * through the Supabase anon client when configured, and falls back to
 * the existing local /traces path otherwise (SUPA-05 escape hatch).
 */

import { getSupabaseClient, isSupabaseConfigured } from "./supabase";
import { api } from "./api";
import type { Trace, TracesResponse } from "./types";

/**
 * Delegate to the existing local traces path.
 * Named so the fallback intent is explicit and grep-able.
 */
async function localTracesFallback(
  limit: number,
  offset: number,
): Promise<TracesResponse> {
  return api.traces(limit, offset);
}

/**
 * Read traces from Supabase (anon key, PostgREST select) when configured,
 * or from the existing local /traces endpoint otherwise.
 *
 * When configured, the full Supabase read chain is:
 *   client.from("traces").select("*").order("created_at", {ascending: false}).range(offset, offset+limit-1)
 *
 * Falls back to the local path when:
 * - isSupabaseConfigured is false (SUPA-05 escape hatch, no Supabase call at all)
 * - getSupabaseClient() returns null (package absent, T-65-12)
 * - The query returns an error (T-65-12 graceful degradation)
 * - Any unexpected throw
 *
 * The return type always matches TracesResponse so callers are unaffected
 * by whether the data came from Supabase or the local path.
 */
export async function tracesFromSupabaseOrLocal(
  limit = 50,
  offset = 0,
): Promise<TracesResponse> {
  if (!isSupabaseConfigured) {
    return localTracesFallback(limit, offset);
  }

  try {
    const client = await getSupabaseClient();
    if (!client) {
      return localTracesFallback(limit, offset);
    }

    const { data, error } = await client
      .from("traces")
      .select("*")
      .order("created_at", { ascending: false })
      .range(offset, offset + limit - 1);

    if (error || !data) {
      return localTracesFallback(limit, offset);
    }

    return { traces: data as Trace[] };
  } catch {
    // Any unexpected error degrades gracefully to local path (T-65-12).
    return localTracesFallback(limit, offset);
  }
}
