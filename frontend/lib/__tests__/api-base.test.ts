/**
 * VERCEL-01 guard tests for the frontend API base path (D-03).
 *
 * These are source-text assertions (no network, no module execution) that pin
 * three invariants the static-export deploy path depends on:
 *
 * 1. Zero bare fetch("/api/ or fetch('/api/ literals anywhere under
 *    frontend/lib. Every dashboard fetch must route through the single
 *    API_BASE constant so NEXT_PUBLIC_API_BASE can retarget the backend.
 * 2. frontend/lib/api.ts derives API_BASE from process.env.NEXT_PUBLIC_API_BASE
 *    (D-01), so a Vercel-hosted bundle can point at a reachable backend.
 * 3. Regression lock (D-02): neither frontend/lib/supabase.ts nor
 *    frontend/lib/supabase-reads.ts references process.env.NEXT_PUBLIC_API_BASE.
 *    This mirrors the Phase 65 ban in supabase-reads.test.ts so this plan
 *    re-pins the separation locally.
 *
 * Source-text style copied from supabase-reads.test.ts (vitest + fs/path).
 */
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const LIB_ROOT = path.resolve(__dirname, "..");

describe("API base wiring (VERCEL-01, D-03)", () => {
  it("has zero bare fetch(\"/api/ literals under frontend/lib", () => {
    const offenders: string[] = [];
    const walk = (dir: string) => {
      for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
        const p = path.join(dir, e.name);
        if (e.isDirectory()) {
          if (e.name !== "__tests__" && e.name !== "fixtures") walk(p);
        } else if (/\.tsx?$/.test(e.name)) {
          const src = fs.readFileSync(p, "utf-8");
          if (src.includes('fetch("/api/') || src.includes("fetch('/api/")) {
            offenders.push(p);
          }
        }
      }
    };
    walk(LIB_ROOT);
    expect(offenders).toEqual([]);
  });

  it("derives API_BASE from process.env.NEXT_PUBLIC_API_BASE in api.ts (D-01)", () => {
    const apiSrc = fs.readFileSync(path.join(LIB_ROOT, "api.ts"), "utf-8");
    expect(apiSrc).toContain("process.env.NEXT_PUBLIC_API_BASE");
  });

  it("keeps NEXT_PUBLIC_API_BASE out of the supabase modules (D-02 regression lock)", () => {
    const supabaseSrc = fs.readFileSync(
      path.join(LIB_ROOT, "supabase.ts"),
      "utf-8",
    );
    const readsSrc = fs.readFileSync(
      path.join(LIB_ROOT, "supabase-reads.ts"),
      "utf-8",
    );
    expect(supabaseSrc).not.toContain("process.env.NEXT_PUBLIC_API_BASE");
    expect(readsSrc).not.toContain("process.env.NEXT_PUBLIC_API_BASE");
  });
});
