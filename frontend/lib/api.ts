/**
 * Typed API client for the horus-os dashboard.
 *
 * Everything runs in the browser. The client fetches the `/api/*` contract at
 * runtime. Two fallbacks keep the static export fully functional without a
 * backend:
 *
 *  1. Demo mode: when NEXT_PUBLIC_HORUS_DEMO === "1", bundled fixtures are
 *     served directly and no network request is made. This powers the static
 *     marketing demo.
 *  2. Graceful fallback: when a real `/api` fetch fails (offline, no backend),
 *     the client falls back to the same fixtures so the UI still renders.
 */

import type {
  ActivityResponse,
  AgentDetailResponse,
  CostByAgentResponse,
  CostByModelResponse,
  HealthResponse,
  IntegrationsResponse,
  LatencyResponse,
  MemoryNoteDetail,
  MemoryResponse,
  SettingsResponse,
  TasksResponse,
  TeamResponse,
  ToolReliabilityResponse,
  Trace,
  TraceChildrenResponse,
  TracesResponse,
} from "./types";

import teamFixture from "./fixtures/team.json";
import agentDetailFixture from "./fixtures/agent-detail.json";
import memoryFixture from "./fixtures/memory.json";
import activityFixture from "./fixtures/activity.json";
import healthFixture from "./fixtures/health.json";
import settingsFixture from "./fixtures/settings.json";
import tracesFixture from "./fixtures/traces.json";
import observabilityFixture from "./fixtures/observability.json";
import integrationsFixture from "./fixtures/integrations.json";
import tasksFixture from "./fixtures/tasks.json";

const DEMO =
  typeof process !== "undefined" &&
  process.env.NEXT_PUBLIC_HORUS_DEMO === "1";

/**
 * Base path for the API (VERCEL-01, D-01).
 *
 * Derived from NEXT_PUBLIC_API_BASE so a deployed (for example Vercel-hosted)
 * static bundle can target a reachable backend. When the var is unset the value
 * resolves to "/api", byte-for-byte today's same-origin local-dev behavior; a
 * configured backend origin (for example https://your-backend.example) yields
 * that origin plus "/api". A single trailing slash on the configured value is
 * stripped first so a base ending in "/" cannot produce a malformed "//api".
 * The typeof-process guard keeps SSR/jsdom green, matching the DEMO read above.
 */
const API_ORIGIN =
  typeof process !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/+$/, "")
    : "";
const API_BASE = `${API_ORIGIN}/api`;

const team = teamFixture as TeamResponse;
const agentDetails = agentDetailFixture as Record<string, AgentDetailResponse>;
const memory = memoryFixture as MemoryResponse;
const activity = activityFixture as ActivityResponse;
const health = healthFixture as HealthResponse;
const settings = settingsFixture as SettingsResponse;
const integrationsData = integrationsFixture as IntegrationsResponse;

interface TracesFixture {
  traces: Trace[];
  children: Record<string, Trace[]>;
}
const traces = tracesFixture as TracesFixture;

const tasks = tasksFixture as TasksResponse;

interface ObservabilityFixture {
  cost: CostByAgentResponse;
  costByModel: CostByModelResponse;
  latency: LatencyResponse;
  tools: ToolReliabilityResponse;
}
const observability = observabilityFixture as ObservabilityFixture;

/**
 * Demo-mode markdown for the curated notes. The runtime serves the real file
 * body; here we ship enough prose so the Memory page reads naturally with no
 * backend. Falls back to a preview-derived stub for unknown paths.
 */
const NOTE_MARKDOWN: Record<string, string> = {
  "notes/welcome-to-horus-os.md": `# Welcome to horus-os

Start here. This note lives in your agents' shared memory, the same place every
note on this page comes from.

## How memory works

Your agents read and write plain markdown notes. Nothing is hidden in a binary
format, and nothing leaves your machine. Everything an agent learns or records
shows up here for you to browse and search.

- Search the box on the left to filter notes by title or content.
- Click any note to read it rendered on the right.
- [[Team Charter]] and [[Project Overview]] are good places to go next.

## What to do next

1. Open the [[Project Overview]] to see the shape of the system.
2. Skim the [[Release Checklist]] before you ship.
3. Head to the Team page to meet the agents that write these notes.

#welcome #memory #getting-started
`,
  "notes/project-overview.md": `# Project Overview

horus-os is a self-hosted autonomous command center. The runtime is Python with
SQLite for persistence, and this dashboard is a static Next.js export bundled
with the runtime.

## Pieces

- A small agent runtime that calls your chosen LLM providers directly.
- A notes store that doubles as shared agent memory.
- This dashboard, served locally or fully offline in demo mode.

#overview #architecture
`,
  "notes/team-charter.md": `# Team Charter

Five starter agents coordinate around a shared goal queue. The Coordinator
delegates, specialists execute, and every run is traced.

## The team

- Coordinator routes goals and tracks progress.
- Engineer writes and reviews code.
- Researcher gathers and verifies sources.
- Writer drafts and edits prose.
- Operator handles schedules and maintenance.

#team #charter
`,
  "notes/release-checklist.md": `# Release Checklist

- [ ] Run the full test suite.
- [ ] Update the changelog.
- [ ] Tag the version.
- [ ] Verify the static export builds clean.

#release #checklist
`,
};

/** Lowercase slug used to key fixtures and route detail lookups. */
export function agentSlug(name: string): string {
  return name.toLowerCase().replace(/\s+/g, "-");
}

/**
 * Fetch JSON from the API, falling back to a bundled fixture on any failure.
 * In demo mode the fetch is skipped entirely.
 */
async function getJson<T>(path: string, fallback: () => T): Promise<T> {
  if (DEMO) return fallback();
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as T;
  } catch {
    // No backend reachable: serve the fixture so the UI still renders.
    return fallback();
  }
}

function fallbackAgentDetail(name: string): AgentDetailResponse {
  const slug = agentSlug(name);
  const detail = agentDetails[slug];
  if (detail) return detail;
  // Build a minimal detail from the team fixture if the slug is unknown.
  const summary = team.agents.find((a) => agentSlug(a.name) === slug);
  if (!summary) {
    throw new Error(`Unknown agent: ${name}`);
  }
  return {
    agent: { ...summary, system_prompt: "" },
    soul_markdown: null,
    recent_traces: [],
  };
}

function fallbackMemoryNote(path: string): MemoryNoteDetail {
  const note = memory.notes.find((n) => n.path === path);
  const markdown =
    NOTE_MARKDOWN[path] ??
    (note?.preview
      ? `# ${note.title}\n\n${note.preview}`
      : "# Note\n\nNo content available in demo mode.");
  return {
    path,
    title: note?.title ?? path,
    markdown,
    modified_at: note?.modified_at ?? new Date(0).toISOString(),
    is_example: false,
  };
}

export const api = {
  team(): Promise<TeamResponse> {
    return getJson<TeamResponse>("/team", () => team);
  },

  agent(name: string): Promise<AgentDetailResponse> {
    const slug = agentSlug(name);
    return getJson<AgentDetailResponse>(
      `/team/${encodeURIComponent(slug)}`,
      () => fallbackAgentDetail(name),
    );
  },

  memory(query = ""): Promise<MemoryResponse> {
    const qs = query ? `?q=${encodeURIComponent(query)}` : "";
    return getJson<MemoryResponse>(`/memory${qs}`, () => {
      if (!query) return memory;
      const q = query.toLowerCase();
      return {
        notes: memory.notes.filter(
          (n) =>
            n.title.toLowerCase().includes(q) ||
            n.preview.toLowerCase().includes(q),
        ),
      };
    });
  },

  memoryNote(path: string): Promise<MemoryNoteDetail> {
    return getJson<MemoryNoteDetail>(
      `/memory/note?path=${encodeURIComponent(path)}`,
      () => fallbackMemoryNote(path),
    );
  },

  activity(limit = 50): Promise<ActivityResponse> {
    return getJson<ActivityResponse>(`/activity?limit=${limit}`, () => ({
      events: activity.events.slice(0, limit),
    }));
  },

  health(): Promise<HealthResponse> {
    return getJson<HealthResponse>("/health", () => health);
  },

  settings(): Promise<SettingsResponse> {
    return getJson<SettingsResponse>("/settings", () => settings);
  },

  integrations(): Promise<IntegrationsResponse> {
    return getJson<IntegrationsResponse>("/integrations", () => integrationsData);
  },

  async saveCredential(
    name: string,
    value: string,
  ): Promise<{ ok: boolean }> {
    if (DEMO) throw new Error("credential management is disabled in demo mode");
    const res = await fetch(
      `${API_BASE}/integrations/${encodeURIComponent(name)}/keys`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value }),
      },
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json() as Promise<{ ok: boolean }>;
  },

  async verifyIntegration(
    name: string,
  ): Promise<{ ok: boolean; error?: string | null }> {
    if (DEMO) throw new Error("verification is disabled in demo mode");
    const res = await fetch(
      `${API_BASE}/integrations/${encodeURIComponent(name)}/verify`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      },
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json() as Promise<{ ok: boolean; error?: string | null }>;
  },

  traces(limit = 50, offset = 0): Promise<TracesResponse> {
    return getJson<TracesResponse>(
      `/traces?limit=${limit}&offset=${offset}`,
      () => ({ traces: traces.traces.slice(offset, offset + limit) }),
    );
  },

  traceChildren(traceId: string): Promise<TraceChildrenResponse> {
    return getJson<TraceChildrenResponse>(
      `/traces/${encodeURIComponent(traceId)}/children`,
      () => ({ children: traces.children[traceId] ?? [] }),
    );
  },

  tasks(status = ""): Promise<TasksResponse> {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return getJson<TasksResponse>(`/tasks${qs}`, () =>
      status
        ? { tasks: tasks.tasks.filter((t) => t.status === status) }
        : tasks,
    );
  },

  async deleteTask(taskId: string): Promise<void> {
    if (DEMO) throw new Error("task deletion is disabled in demo mode");
    const res = await fetch(
      `${API_BASE}/tasks/${encodeURIComponent(taskId)}`,
      { method: "DELETE" },
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  },

  async deleteTrace(traceId: string): Promise<void> {
    if (DEMO) throw new Error("trace deletion is disabled in demo mode");
    const res = await fetch(
      `${API_BASE}/traces/${encodeURIComponent(traceId)}`,
      { method: "DELETE" },
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  },

  costByAgent(since = "7d"): Promise<CostByAgentResponse> {
    return getJson<CostByAgentResponse>(
      `/observability/cost?since=${encodeURIComponent(since)}`,
      () => observability.cost,
    );
  },

  costByModel(since = "7d"): Promise<CostByModelResponse> {
    return getJson<CostByModelResponse>(
      `/observability/cost-by-model?since=${encodeURIComponent(since)}`,
      () => observability.costByModel,
    );
  },

  latency(since = "7d"): Promise<LatencyResponse> {
    return getJson<LatencyResponse>(
      `/observability/latency?since=${encodeURIComponent(since)}`,
      () => observability.latency,
    );
  },

  tools(since = "7d"): Promise<ToolReliabilityResponse> {
    return getJson<ToolReliabilityResponse>(
      `/observability/tools?since=${encodeURIComponent(since)}`,
      () => observability.tools,
    );
  },
};

export const isDemoMode = DEMO;
