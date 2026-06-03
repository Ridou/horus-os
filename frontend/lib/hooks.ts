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
