"use client";

import type { Agent } from "@/lib/types";
import { agentSlug } from "@/lib/api";
import { cn } from "@/lib/cn";
import { StatusIcon } from "@/components/StatusIcon";

interface OrgViewProps {
  agents: Agent[];
  selectedSlug: string | null;
  onSelect: (slug: string) => void;
}

function AgentNode({
  agent,
  selected,
  onSelect,
  lead,
}: {
  agent: Agent;
  selected: boolean;
  onSelect: (slug: string) => void;
  lead?: boolean;
}) {
  const slug = agentSlug(agent.name);
  return (
    <button
      type="button"
      onClick={() => onSelect(slug)}
      className={cn(
        "flex w-44 flex-col items-center gap-1.5 border bg-bg-secondary px-3 py-3 text-center transition-colors border-glow",
        selected ? "border-accent-cyan" : "border-border-subtle",
        lead && "glow-cyan",
      )}
    >
      <span
        className="h-3 w-3 rounded-full"
        style={{ backgroundColor: agent.color }}
      />
      <span className="flex items-center gap-1.5 text-sm font-medium text-text-primary">
        {agent.name}
        <StatusIcon status={agent.status} />
      </span>
      <span className="line-clamp-2 text-[10px] text-text-muted">
        {agent.description}
      </span>
    </button>
  );
}

/**
 * Simple org chart. The Coordinator (if present) sits on top; everyone else
 * is rendered as a direct report beneath, connected by a thin rule.
 */
export function OrgView({ agents, selectedSlug, onSelect }: OrgViewProps) {
  const lead =
    agents.find((a) => a.name.toLowerCase() === "coordinator") ?? agents[0];
  const reports = agents.filter((a) => a !== lead);

  if (!lead) return null;

  return (
    <div className="flex flex-col items-center gap-8 py-10">
      <AgentNode
        agent={lead}
        lead
        selected={selectedSlug === agentSlug(lead.name)}
        onSelect={onSelect}
      />

      {reports.length > 0 && (
        <>
          {/* Connector */}
          <div className="h-6 w-px bg-border-subtle" />
          <div className="flex flex-wrap items-start justify-center gap-4">
            {reports.map((agent) => (
              <AgentNode
                key={agent.name}
                agent={agent}
                selected={selectedSlug === agentSlug(agent.name)}
                onSelect={onSelect}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default OrgView;
