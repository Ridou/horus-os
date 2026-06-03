/**
 * Tests for frontend/lib/supabase.ts - the SUPA-04 anon-only Supabase browser client.
 *
 * Covers:
 * - isSupabaseConfigured is false when either env var is unset
 * - getSupabaseClient() resolves to null when not configured (no import, no throw)
 * - getSupabaseClient() resolves to null when configured but package absent (graceful)
 * - Source-text assertion: no SUPABASE_SERVICE_KEY reference in the module
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import * as fs from "fs";
import * as path from "path";

describe("supabase client module", () => {
  const originalUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const originalKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    // Restore env vars
    if (originalUrl === undefined) {
      delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    } else {
      process.env.NEXT_PUBLIC_SUPABASE_URL = originalUrl;
    }
    if (originalKey === undefined) {
      delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    } else {
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = originalKey;
    }
  });

  it("isSupabaseConfigured is false when both vars are unset", async () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    const mod = await import("../supabase");
    expect(mod.isSupabaseConfigured).toBe(false);
  });

  it("getSupabaseClient resolves to null when not configured", async () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    const mod = await import("../supabase");
    const client = await mod.getSupabaseClient();
    expect(client).toBeNull();
  });

  it("getSupabaseClient resolves to null without throwing when configured but package absent", async () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://test.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "test-anon-key";
    const mod = await import("../supabase");
    // @supabase/supabase-js is not installed; dynamic import fails gracefully
    const client = await mod.getSupabaseClient();
    expect(client).toBeNull();
  });

  it("isSupabaseConfigured is true when both vars are set", async () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://test.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "test-anon-key";
    const mod = await import("../supabase");
    expect(mod.isSupabaseConfigured).toBe(true);
  });

  it("source text has no env-var access for SUPABASE_SERVICE_KEY (SUPA-02 / T-65-11)", () => {
    const modulePath = path.resolve(__dirname, "../supabase.ts");
    const source = fs.readFileSync(modulePath, "utf-8");
    // The service key must never be read as an env var in browser code.
    // These patterns cover both NEXT_PUBLIC_ naming violations and direct reads.
    expect(source).not.toContain("process.env.SUPABASE_SERVICE_KEY");
    expect(source).not.toContain("process.env.NEXT_PUBLIC_SUPABASE_SERVICE");
    // No import or assignment of the service key name
    expect(source).not.toMatch(/NEXT_PUBLIC_SUPABASE_SERVICE_KEY/);
  });
});
