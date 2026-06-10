/** Stable React Query cache keys for the dashboard. */
export const queryKeys = {
  team: () => ["team"] as const,
  agents: () => ["agents"] as const,
  agent: (name: string) => ["agent", name] as const,
  memory: (query: string) => ["memory", query] as const,
  memoryNote: (path: string) => ["memory-note", path] as const,
  activity: (limit: number) => ["activity", limit] as const,
  health: () => ["health"] as const,
  settings: () => ["settings"] as const,
  traces: (limit: number, offset: number) =>
    ["traces", limit, offset] as const,
  traceChildren: (traceId: string) => ["trace-children", traceId] as const,
  costByAgent: (since: string) => ["obs-cost", since] as const,
  costByModel: (since: string) => ["obs-cost-by-model", since] as const,
  latency: (since: string) => ["obs-latency", since] as const,
  tools: (since: string) => ["obs-tools", since] as const,
  integrations: () => ["integrations"] as const,
  tasks: (status: string) => ["tasks", status] as const,
  researchProgress: (id: string) => ["research-progress", id] as const,
  researchReport: (id: string) => ["research-report", id] as const,
  storeBundles: () => ["store-bundles"] as const,
  reflections: (view: string, agent: string) =>
    ["reflections", view, agent] as const,
};
