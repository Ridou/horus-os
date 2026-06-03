/**
 * TypeScript types for the horus-os dashboard API contract.
 *
 * Every shape here mirrors a `/api/*` endpoint. The FastAPI runtime implements
 * the server side; the dashboard fetches these at runtime (or falls back to
 * bundled fixtures in demo mode).
 */

/** Canonical agent lifecycle status. */
export type AgentStatus =
  | "active"
  | "running"
  | "paused"
  | "idle"
  | "done"
  | "pending"
  | "error"
  | "blocked";

/** Summary record returned by GET /api/team. */
export interface Agent {
  name: string;
  color: string;
  description: string;
  default_model: string;
  soul_path: string;
  status: AgentStatus;
  trace_count: number;
  last_active_at: string | null;
}

/** GET /api/team */
export interface TeamResponse {
  agents: Agent[];
}

/** A single trace summary attached to an agent detail. */
export interface TraceSummary {
  trace_id: string;
  created_at: string;
  prompt: string;
  status: AgentStatus;
}

/** Full agent detail (extends the summary with the resolved system prompt). */
export interface AgentDetail extends Agent {
  system_prompt: string;
}

/** GET /api/team/{name} */
export interface AgentDetailResponse {
  agent: AgentDetail;
  soul_markdown: string | null;
  recent_traces: TraceSummary[];
}

/** A memory note summary. */
export interface MemoryNote {
  path: string;
  title: string;
  size_bytes: number;
  modified_at: string;
  preview: string;
}

/** GET /api/memory?q= */
export interface MemoryResponse {
  notes: MemoryNote[];
}

/** GET /api/memory/note?path= */
export interface MemoryNoteDetail {
  path: string;
  title: string;
  markdown: string;
  modified_at: string;
  is_example: boolean;
}

/** A single activity-feed event. */
export interface ActivityEvent {
  trace_id: string;
  created_at: string;
  agent: string;
  kind: string;
  summary: string;
  status: AgentStatus;
}

/** GET /api/activity?limit= */
export interface ActivityResponse {
  events: ActivityEvent[];
}

/** GET /api/health */
export interface HealthResponse {
  status: string;
  version: string;
  db_size_bytes: number;
  trace_count: number;
  note_count: number;
  agent_count: number;
}

/** Runtime counts surfaced on the settings page. */
export interface SettingsCounts {
  agents: number;
  notes: number;
  traces: number;
}

/**
 * GET /api/settings
 *
 * Read-only snapshot of the resolved configuration. The runtime owns the
 * source of truth (a TOML file edited via `horus-os init`); the dashboard
 * surfaces it but never writes it back.
 */
export interface SettingsResponse {
  data_dir: string;
  notes_dir: string;
  db_path: string;
  default_provider: string;
  anthropic_model: string;
  gemini_model: string;
  schema_version: number;
  version: string;
  counts: SettingsCounts;
}

/** A single tool invocation the model requested, as carried on a trace. */
export interface TraceToolUse {
  id: string;
  name: string;
  input: Record<string, unknown>;
}

/**
 * One persisted agent invocation. Mirrors the runtime TraceRecord dataclass
 * serialized by GET /api/traces and GET /api/traces/{id}/children.
 */
export interface Trace {
  trace_id: string;
  created_at: string;
  provider: string;
  model: string;
  prompt: string;
  response_text: string;
  tool_uses: TraceToolUse[];
  usage: Record<string, number>;
  latency_ms: number | null;
  status: string;
  error_message: string | null;
  parent_trace_id: string | null;
  agent_profile_name: string | null;
}

/** GET /api/traces?limit=&offset= */
export interface TracesResponse {
  traces: Trace[];
}

/** GET /api/traces/{id}/children */
export interface TraceChildrenResponse {
  children: Trace[];
}

/** One row from GET /api/observability/cost. */
export interface CostByAgentRow {
  agent: string;
  total_cost_usd: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cache_read_input_tokens: number;
  total_cache_creation_input_tokens: number;
  run_count: number;
  uncosted_runs: number;
}

/** GET /api/observability/cost?since= */
export interface CostByAgentResponse {
  agents: CostByAgentRow[];
}

/** One row from GET /api/observability/cost-by-model. */
export interface CostByModelRow {
  model: string;
  provider: string;
  total_cost_usd: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cache_read_input_tokens: number;
  total_cache_creation_input_tokens: number;
  call_count: number;
  uncosted_calls: number;
}

/** GET /api/observability/cost-by-model?since= */
export interface CostByModelResponse {
  models: CostByModelRow[];
}

/**
 * GET /api/observability/latency?since=
 *
 * Percentiles are null when sample_count is 0; callers apply the n>=10
 * render rule before trusting a small-sample percentile.
 */
export interface LatencyResponse {
  p50_ms: number | null;
  p95_ms: number | null;
  sample_count: number;
}

/** One row from GET /api/observability/tools. */
export interface ToolReliabilityRow {
  tool_name: string;
  call_count: number;
  success_count: number;
  error_count: number;
  retry_then_success_count: number;
  expected_no_result_count: number;
  success_rate: number | null;
  last_error_type: string | null;
  last_error_at: string | null;
}

/** GET /api/observability/tools?since= */
export interface ToolReliabilityResponse {
  tools: ToolReliabilityRow[];
}

/** Live status of a single integration connector. */
export type IntegrationStatusState =
  | "verified"
  | "configured-unverified"
  | "missing"
  | "error";

/** One integration connector row returned by GET /api/integrations. */
export interface IntegrationStatus {
  id: string;
  name: string;
  category: string;
  description: string;
  status: IntegrationStatusState;
  env_var: string;
  /** All env var names required for this integration (names only, never values). */
  required_vars: string[];
  credential_portal_url: string;
}

/** GET /api/integrations */
export interface IntegrationsResponse {
  integrations: IntegrationStatus[];
  demo_mode: boolean;
}

/** One task row returned by GET /api/tasks. */
export interface Task {
  task_id: string;
  title: string;
  description: string;
  status: "pending" | "running" | "completed" | "error" | "cancelled";
  agent_profile_name: string | null;
  created_at: string;
  updated_at: string;
}

/** GET /api/tasks */
export interface TasksResponse {
  tasks: Task[];
}
