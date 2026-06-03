/**
 * Tests for frontend/lib/supabase-reads.ts - the SUPA-04 real anon read path.
 *
 * All Supabase and API calls are mocked; no live connection is required.
 *
 * Uses vi.resetModules + vi.doMock in beforeEach for per-test isolation
 * (vi.mock hoists prevent per-test scoping - same pattern as 61-02).
 *
 * Covers:
 * - CONFIGURED: traces come from the mocked Supabase anon client; local api.traces NOT called
 * - NOT CONFIGURED: local api.traces is called; Supabase client is never invoked
 * - CONFIGURED-but-error: Supabase query returns an error; falls back to local path (T-65-12)
 * - Source-text: neither supabase.ts nor supabase-reads.ts uses service key or NEXT_PUBLIC_API_BASE
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import * as fs from "fs";
import * as path from "path";
import type { Trace, TracesResponse } from "../types";

// ---- Fake data ----

const FAKE_SUPABASE_TRACE: Trace = {
  trace_id: "supabase-row",
  created_at: "2026-01-01T00:00:00Z",
  provider: "anthropic",
  model: "claude-3-5-sonnet",
  prompt: "Hello from Supabase",
  response_text: "Supabase response",
  tool_uses: [],
  usage: {},
  latency_ms: 100,
  status: "ok",
  error_message: null,
  parent_trace_id: null,
  agent_profile_name: null,
};

const LOCAL_SENTINEL_TRACE: Trace = {
  trace_id: "local-sentinel",
  created_at: "2026-01-01T00:00:00Z",
  provider: "anthropic",
  model: "claude-3-5-sonnet",
  prompt: "Hello from local",
  response_text: "Local response",
  tool_uses: [],
  usage: {},
  latency_ms: 50,
  status: "ok",
  error_message: null,
  parent_trace_id: null,
  agent_profile_name: null,
};

const LOCAL_SENTINEL: TracesResponse = { traces: [LOCAL_SENTINEL_TRACE] };

// ---- Helper: build a fake Supabase query chain ----

function makeFakeClient(
  data: Trace[] | null,
  error: { message: string } | null,
) {
  const range = vi.fn().mockResolvedValue({ data, error });
  const order = vi.fn().mockReturnValue({ range });
  const select = vi.fn().mockReturnValue({ order });
  const from = vi.fn().mockReturnValue({ select });
  return { from, _mocks: { select, order, range } };
}

// ---- Tests ----

describe("tracesFromSupabaseOrLocal", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("CONFIGURED: reads from Supabase and does not call local api.traces", async () => {
    const apiTracesMock = vi.fn().mockResolvedValue(LOCAL_SENTINEL);
    const fakeClient = makeFakeClient([FAKE_SUPABASE_TRACE], null);
    const getClientMock = vi.fn().mockResolvedValue(fakeClient);

    vi.doMock("../supabase", () => ({
      isSupabaseConfigured: true,
      getSupabaseClient: getClientMock,
    }));
    vi.doMock("../api", () => ({
      api: { traces: apiTracesMock },
    }));

    const { tracesFromSupabaseOrLocal } = await import("../supabase-reads");
    const result = await tracesFromSupabaseOrLocal();

    expect(result.traces).toHaveLength(1);
    expect(result.traces[0].trace_id).toBe("supabase-row");
    expect(apiTracesMock).not.toHaveBeenCalled();
  });

  it("NOT CONFIGURED: reads from local and does not invoke Supabase client", async () => {
    const getClientMock = vi.fn();
    const apiTracesMock = vi.fn().mockResolvedValue(LOCAL_SENTINEL);

    vi.doMock("../supabase", () => ({
      isSupabaseConfigured: false,
      getSupabaseClient: getClientMock,
    }));
    vi.doMock("../api", () => ({
      api: { traces: apiTracesMock },
    }));

    const { tracesFromSupabaseOrLocal } = await import("../supabase-reads");
    const result = await tracesFromSupabaseOrLocal();

    expect(result.traces[0].trace_id).toBe("local-sentinel");
    expect(getClientMock).not.toHaveBeenCalled();
  });

  it("CONFIGURED-but-error: falls back to local path (T-65-12 graceful degradation)", async () => {
    const fakeClient = makeFakeClient(null, { message: "boom" });
    const getClientMock = vi.fn().mockResolvedValue(fakeClient);
    const apiTracesMock = vi.fn().mockResolvedValue(LOCAL_SENTINEL);

    vi.doMock("../supabase", () => ({
      isSupabaseConfigured: true,
      getSupabaseClient: getClientMock,
    }));
    vi.doMock("../api", () => ({
      api: { traces: apiTracesMock },
    }));

    const { tracesFromSupabaseOrLocal } = await import("../supabase-reads");
    const result = await tracesFromSupabaseOrLocal();

    expect(result.traces[0].trace_id).toBe("local-sentinel");
    expect(apiTracesMock).toHaveBeenCalledTimes(1);
  });

  it("source text: no service-key usage or NEXT_PUBLIC_API_BASE usage in either module (T-65-11, T-65-13)", () => {
    const supabaseModulePath = path.resolve(__dirname, "../supabase.ts");
    const readsModulePath = path.resolve(__dirname, "../supabase-reads.ts");

    const supabaseSrc = fs.readFileSync(supabaseModulePath, "utf-8");
    const readsSrc = fs.readFileSync(readsModulePath, "utf-8");

    // No env-var access (process.env) for service key in either file.
    // These patterns catch both NEXT_PUBLIC_ naming violations and direct reads.
    expect(supabaseSrc).not.toContain("process.env.SUPABASE_SERVICE_KEY");
    expect(supabaseSrc).not.toContain("process.env.NEXT_PUBLIC_SUPABASE_SERVICE");
    expect(supabaseSrc).not.toMatch(/NEXT_PUBLIC_SUPABASE_SERVICE_KEY/);
    expect(readsSrc).not.toContain("process.env.SUPABASE_SERVICE_KEY");
    expect(readsSrc).not.toContain("process.env.NEXT_PUBLIC_SUPABASE_SERVICE");
    expect(readsSrc).not.toMatch(/NEXT_PUBLIC_SUPABASE_SERVICE_KEY/);

    // Deploy-time switching is Phase 67; assert process.env usage is absent (T-65-13).
    // Comments may mention the name for documentation - only env reads are forbidden.
    expect(supabaseSrc).not.toContain("process.env.NEXT_PUBLIC_API_BASE");
    expect(readsSrc).not.toContain("process.env.NEXT_PUBLIC_API_BASE");
  });
});
