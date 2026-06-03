"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { queryKeys } from "./query-keys";

/** GET /api/team */
export function useTeam() {
  return useQuery({
    queryKey: queryKeys.team(),
    queryFn: () => api.team(),
  });
}

/** GET /api/agents: the agent profiles available to chat with. */
export function useAgents() {
  return useQuery({
    queryKey: queryKeys.agents(),
    queryFn: () => api.agents(),
  });
}

/** GET /api/team/{name}. Disabled until a name is selected. */
export function useAgent(name: string | null) {
  return useQuery({
    queryKey: queryKeys.agent(name ?? ""),
    queryFn: () => api.agent(name as string),
    enabled: !!name,
  });
}

/** GET /api/memory?q= */
export function useMemory(query = "") {
  return useQuery({
    queryKey: queryKeys.memory(query),
    queryFn: () => api.memory(query),
  });
}

/** GET /api/memory/note?path= */
export function useMemoryNote(path: string | null) {
  return useQuery({
    queryKey: queryKeys.memoryNote(path ?? ""),
    queryFn: () => api.memoryNote(path as string),
    enabled: !!path,
  });
}

/** GET /api/activity?limit= */
export function useActivity(limit = 50) {
  return useQuery({
    queryKey: queryKeys.activity(limit),
    queryFn: () => api.activity(limit),
  });
}

/** GET /api/health */
export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health(),
    queryFn: () => api.health(),
  });
}

/** GET /api/settings */
export function useSettings() {
  return useQuery({
    queryKey: queryKeys.settings(),
    queryFn: () => api.settings(),
  });
}

/** GET /api/integrations */
export function useIntegrations() {
  return useQuery({
    queryKey: queryKeys.integrations(),
    queryFn: () => api.integrations(),
  });
}

/** GET /api/traces?limit=&offset= */
export function useTraces(limit = 50, offset = 0) {
  return useQuery({
    queryKey: queryKeys.traces(limit, offset),
    queryFn: () => api.traces(limit, offset),
  });
}

/** GET /api/traces/{id}/children. Disabled until a trace id is provided. */
export function useTraceChildren(traceId: string | null) {
  return useQuery({
    queryKey: queryKeys.traceChildren(traceId ?? ""),
    queryFn: () => api.traceChildren(traceId as string),
    enabled: !!traceId,
  });
}

/** GET /api/observability/cost?since= */
export function useCostByAgent(since = "7d") {
  return useQuery({
    queryKey: queryKeys.costByAgent(since),
    queryFn: () => api.costByAgent(since),
  });
}

/** GET /api/observability/cost-by-model?since= */
export function useCostByModel(since = "7d") {
  return useQuery({
    queryKey: queryKeys.costByModel(since),
    queryFn: () => api.costByModel(since),
  });
}

/** GET /api/observability/latency?since= */
export function useLatency(since = "7d") {
  return useQuery({
    queryKey: queryKeys.latency(since),
    queryFn: () => api.latency(since),
  });
}

/** GET /api/observability/tools?since= */
export function useTools(since = "7d") {
  return useQuery({
    queryKey: queryKeys.tools(since),
    queryFn: () => api.tools(since),
  });
}

/** GET /api/tasks?status= */
export function useTasks(status = "") {
  return useQuery({
    queryKey: queryKeys.tasks(status),
    queryFn: () => api.tasks(status),
  });
}

/** Phases that mean the run has stopped; once reached, polling halts. */
const TERMINAL_PHASES = new Set(["done", "cancelled", "error"]);

/**
 * GET /api/research/{id}/progress. Disabled until a task id exists; while the
 * run is in flight it polls every two seconds and stops once the phase is
 * terminal (done / cancelled / error). Powers the live progress panel.
 */
export function useResearchProgress(taskId: string | null) {
  return useQuery({
    queryKey: queryKeys.researchProgress(taskId ?? ""),
    queryFn: () => api.researchProgress(taskId as string),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const phase = query.state.data?.phase;
      return phase && TERMINAL_PHASES.has(phase) ? false : 2000;
    },
  });
}

/**
 * GET /api/research/{id}/report. Enabled only once the run has completed, so
 * the report (404/409 until done) is never fetched early.
 */
export function useResearchReport(taskId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.researchReport(taskId ?? ""),
    queryFn: () => api.researchReport(taskId as string),
    enabled: !!taskId && enabled,
  });
}
