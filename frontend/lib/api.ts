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
  ChatAgentsResponse,
  ChatStreamEvent,
  ChatStreamRequest,
  CreateAgentRequest,
  CostByAgentResponse,
  CostByModelResponse,
  HealthResponse,
  IntegrationsResponse,
  LatencyResponse,
  MemoryNoteDetail,
  MemoryResponse,
  ReflectionsResponse,
  ReflectionView,
  ResearchProgress,
  ResearchReport,
  ResearchStartResponse,
  SettingsResponse,
  StoreBundle,
  StoreBundleDetail,
  StoreBundlesResponse,
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
import researchFixture from "./fixtures/research.json";
import reflectionsFixture from "./fixtures/reflections.json";

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
 * Bundled Deep Research demo data. One representative plan, a mid-run progress
 * snapshot, and a finished cited report so the /research page renders fully in
 * demo mode and when no backend is reachable.
 */
interface ResearchFixture {
  task_id: string;
  trace_id: string;
  status: "pending" | "running";
  plan: ResearchStartResponse["plan"];
  progress: ResearchProgress;
  report: string;
}
const research = researchFixture as ResearchFixture;

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

/**
 * Demo-mode catalog of featured agent bundles. Mirrors the backend store so
 * the page renders fully with no server (the install action stays disabled in
 * demo). The full personas live server-side; these summaries drive the grid.
 */
const STORE_FIXTURE: StoreBundle[] = [
  {
    slug: "atlas",
    name: "Atlas",
    color: "#38bdf8",
    role: "Travel planner",
    description: "Plans trips, finds places to go, and handles travel logistics.",
    default_model: null,
    recommended_tools: ["web_search", "create_calendar_event", "create_note"],
    recommended_adapters: ["calendar", "voice"],
    installed: false,
  },
  {
    slug: "vitriol",
    name: "Vitriol",
    color: "#34d399",
    role: "Wellness researcher",
    description:
      "Evidence-first wellness and integrative-health information. Not medical advice.",
    default_model: null,
    recommended_tools: ["web_search", "search_notes", "create_note"],
    recommended_adapters: ["web"],
    installed: false,
  },
  {
    slug: "sol",
    name: "Sol",
    color: "#f59e0b",
    role: "Reflective companion",
    description: "A reflective conversational companion and journaling partner.",
    default_model: null,
    recommended_tools: ["search_notes", "create_note", "append_note"],
    recommended_adapters: [],
    installed: false,
  },
];

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

const reflectionsData = reflectionsFixture as ReflectionsResponse;

/**
 * View + agent filtering applied to the bundled reflections fixture, so the
 * Standup section renders in demo mode and whenever the /api/reflections
 * endpoint is not yet reachable. Mirrors the intended server-side view logic.
 */
function selectReflections(
  view: ReflectionView,
  agent: string,
): ReflectionsResponse {
  const base = agent
    ? reflectionsData.reflections.filter((r) => r.agent_profile_name === agent)
    : reflectionsData.reflections;
  if (view === "growth") {
    return {
      reflections: base
        .filter((r) => r.category === "win" || r.status === "done")
        .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    };
  }
  if (view === "decisions") {
    return {
      reflections: base
        .filter(
          (r) =>
            r.status === "accepted" ||
            r.status === "done" ||
            r.status === "dismissed",
        )
        .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    };
  }
  // feed: active items, most important first.
  return {
    reflections: base
      .filter((r) => r.status === "open" || r.status === "acknowledged")
      .sort(
        (a, b) =>
          b.importance - a.importance || b.created_at.localeCompare(a.created_at),
      ),
  };
}

export const api = {
  team(): Promise<TeamResponse> {
    return getJson<TeamResponse>("/team", () => team);
  },

  /** GET /api/store: installable agent bundles, flagged installed/not. */
  storeBundles(): Promise<StoreBundlesResponse> {
    return getJson<StoreBundlesResponse>("/store", () => ({
      bundles: STORE_FIXTURE,
    }));
  },

  /** GET /api/store/{slug}: a bundle in full, including the persona. */
  storeBundle(slug: string): Promise<StoreBundleDetail> {
    return getJson<StoreBundleDetail>(
      `/store/${encodeURIComponent(slug)}`,
      () => {
        const b = STORE_FIXTURE.find((x) => x.slug === slug) ?? STORE_FIXTURE[0];
        return { ...b, system_prompt: "", setup_notes: "" };
      },
    );
  },

  /** POST /api/store/{slug}/install: create an agent from a bundle. */
  async installBundle(slug: string): Promise<{ name: string }> {
    if (DEMO) throw new Error("install is disabled in demo mode");
    const res = await fetch(
      `${API_BASE}/store/${encodeURIComponent(slug)}/install`,
      { method: "POST", headers: { "Content-Type": "application/json" } },
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json() as Promise<{ name: string }>;
  },

  /** POST /api/agents: create a custom agent (the builder). */
  async createAgent(payload: CreateAgentRequest): Promise<{ name: string }> {
    if (DEMO) throw new Error("creating agents is disabled in demo mode");
    const res = await fetch(`${API_BASE}/agents`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const detail =
        res.status === 409
          ? "An agent with that name already exists."
          : `HTTP ${res.status}`;
      throw new Error(detail);
    }
    return res.json() as Promise<{ name: string }>;
  },

  /**
   * GET /api/agents: the agent profiles you can chat with. Falls back to the
   * team fixture (mapped to the lighter agents shape) so the chat picker still
   * lists the starter team in demo mode and when no backend is reachable.
   */
  agents(): Promise<ChatAgentsResponse> {
    return getJson<ChatAgentsResponse>("/agents", () => ({
      agents: team.agents.map((a) => ({
        name: a.name,
        default_model: a.default_model,
      })),
    }));
  },

  /**
   * POST /api/chat/stream: send a prompt and stream the reply as Server-Sent
   * Events. Each parsed frame (token, tool_call, done, error) is delivered to
   * onEvent. Mutating and backend-only, so it throws in demo mode. Pass an
   * AbortSignal to stop the run mid-stream.
   */
  async chatStream(
    body: ChatStreamRequest,
    onEvent: (event: ChatStreamEvent) => void,
    signal?: AbortSignal,
  ): Promise<void> {
    if (DEMO) throw new Error("chat is disabled in demo mode");
    const res = await fetch(`${API_BASE}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // SSE frames are delimited by a blank line. Keep the trailing partial.
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const line = frame.trim();
        if (!line.startsWith("data:")) continue;
        const json = line.slice(line.indexOf(":") + 1).trim();
        try {
          onEvent(JSON.parse(json) as ChatStreamEvent);
        } catch {
          // Skip a malformed frame rather than abort the whole stream.
        }
      }
    }
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

  /**
   * GET /api/reflections?view=feed|growth|decisions&agent=
   *
   * The agents' daily self-improvement reflections that power the Standup
   * section. Falls back to the bundled fixture (filtered to the requested
   * view) so the page renders before the reflection backend exists.
   */
  reflections(
    view: ReflectionView = "feed",
    agent = "",
  ): Promise<ReflectionsResponse> {
    const params = new URLSearchParams({ view });
    if (agent) params.set("agent", agent);
    return getJson<ReflectionsResponse>(
      `/reflections?${params.toString()}`,
      () => selectReflections(view, agent),
    );
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

  /**
   * POST /api/research: plan a run WITHOUT spending tokens (RESEARCH-02
   * plan-before-execute). Returns the plan + task_id; the run starts only on a
   * later startResearchRun call. Mutating, so disabled in demo mode.
   */
  async startResearch(question: string): Promise<ResearchStartResponse> {
    if (DEMO) throw new Error("research is disabled in demo mode");
    const res = await fetch(`${API_BASE}/research`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json() as Promise<ResearchStartResponse>;
  },

  /**
   * POST /api/research/{id}/start: confirm the reviewed plan and schedule the
   * background run. Mutating, so disabled in demo mode.
   */
  async startResearchRun(taskId: string): Promise<{ status: string }> {
    if (DEMO) throw new Error("research is disabled in demo mode");
    const res = await fetch(
      `${API_BASE}/research/${encodeURIComponent(taskId)}/start`,
      { method: "POST", headers: { "Content-Type": "application/json" } },
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json() as Promise<{ status: string }>;
  },

  /**
   * GET /api/research/{id}/progress: the live phase / sources / iteration
   * counts for an in-flight run (RESEARCH-02 live progress). Falls back to the
   * bundled progress snapshot so the panel renders without a backend.
   */
  researchProgress(taskId: string): Promise<ResearchProgress> {
    return getJson<ResearchProgress>(
      `/research/${encodeURIComponent(taskId)}/progress`,
      () => ({ ...research.progress, task_id: taskId }),
    );
  },

  /**
   * GET /api/research/{id}/report: the rendered cited markdown once synthesis
   * completes (RESEARCH-05 reviewable). Falls back to the bundled sample report
   * so the cited render works offline and in demo mode.
   */
  researchReport(taskId: string): Promise<ResearchReport> {
    return getJson<ResearchReport>(
      `/research/${encodeURIComponent(taskId)}/report`,
      () => ({
        task_id: taskId,
        trace_id: research.trace_id,
        report: research.report,
      }),
    );
  },

  /**
   * POST /api/research/{id}/cancel: cancel at the plan stage or mid-run
   * (RESEARCH-05 cancelable). Mutating, so disabled in demo mode.
   */
  async cancelResearch(taskId: string): Promise<void> {
    if (DEMO) throw new Error("research is disabled in demo mode");
    const res = await fetch(
      `${API_BASE}/research/${encodeURIComponent(taskId)}/cancel`,
      { method: "POST", headers: { "Content-Type": "application/json" } },
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
