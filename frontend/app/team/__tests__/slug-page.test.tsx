import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { AgentDetailResponse } from "../../../lib/types";

const coordinatorDetail: AgentDetailResponse = {
  agent: {
    name: "Coordinator",
    color: "#00d4ff",
    description: "Routes incoming goals, delegates to specialists, and tracks progress across the team.",
    default_model: "claude-3-5-haiku-20241022",
    soul_path: "souls/coordinator.md",
    status: "active",
    trace_count: 412,
    last_active_at: "2026-05-30T22:18:00Z",
    system_prompt: "You are the Coordinator.",
  },
  soul_markdown: "# Coordinator\n\nThe Coordinator is the front door of the team.\n\n## Responsibilities\n\n- Decompose a goal into ordered, assignable tasks.\n",
  recent_traces: [
    {
      trace_id: "trc_8f21a0",
      created_at: "2026-05-30T22:18:00Z",
      prompt: "Plan the v0.7 dashboard milestone.",
      status: "done",
    },
  ],
};

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("AgentDetailView (/team/[slug] inner component)", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.doMock("next/navigation", () => ({
      useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
      useSearchParams: () => new URLSearchParams(),
      usePathname: () => "/team/coordinator",
    }));
    vi.doMock("../../../lib/hooks", () => ({
      useAgent: vi.fn().mockReturnValue({
        data: coordinatorDetail,
        isLoading: false,
        isError: false,
      }),
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the agent name in the page heading", async () => {
    const { AgentDetailView } = await import("../[slug]/AgentDetailView");
    render(<AgentDetailView slug="coordinator" />, { wrapper: makeWrapper() });
    // Coordinator appears in PageHeader h1 and in MarkdownRenderer; getAllBy confirms it is present
    const matches = screen.getAllByText("Coordinator");
    expect(matches.length).toBeGreaterThan(0);
  });

  it("renders the Soul section heading", async () => {
    const { AgentDetailView } = await import("../[slug]/AgentDetailView");
    render(<AgentDetailView slug="coordinator" />, { wrapper: makeWrapper() });
    expect(screen.getByText("Soul")).toBeInTheDocument();
  });

  it("renders the soul markdown content heading from MarkdownRenderer", async () => {
    const { AgentDetailView } = await import("../[slug]/AgentDetailView");
    render(<AgentDetailView slug="coordinator" />, { wrapper: makeWrapper() });
    // MarkdownRenderer renders # Coordinator as h1; use getAllByRole since PageHeader also has one
    const headings = screen.getAllByRole("heading", { name: "Coordinator" });
    expect(headings.length).toBeGreaterThan(0);
  });

  it("renders recent traces section heading and a trace prompt", async () => {
    const { AgentDetailView } = await import("../[slug]/AgentDetailView");
    render(<AgentDetailView slug="coordinator" />, { wrapper: makeWrapper() });
    expect(screen.getByText("Recent traces")).toBeInTheDocument();
    expect(screen.getByText("Plan the v0.7 dashboard milestone.")).toBeInTheDocument();
  });

  it("renders agent description", async () => {
    const { AgentDetailView } = await import("../[slug]/AgentDetailView");
    render(<AgentDetailView slug="coordinator" />, { wrapper: makeWrapper() });
    expect(
      screen.getByText("Routes incoming goals, delegates to specialists, and tracks progress across the team."),
    ).toBeInTheDocument();
  });
});

describe("AgentDetailView (error state)", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.doMock("next/navigation", () => ({
      useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
      useSearchParams: () => new URLSearchParams(),
      usePathname: () => "/team/unknown",
    }));
    vi.doMock("../../../lib/hooks", () => ({
      useAgent: vi.fn().mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
      }),
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders error state when agent is not found", async () => {
    const { AgentDetailView } = await import("../[slug]/AgentDetailView");
    render(<AgentDetailView slug="unknown" />, { wrapper: makeWrapper() });
    expect(screen.getByText("Could not load this agent.")).toBeInTheDocument();
  });
});

describe("AgentDetailView (loading state)", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.doMock("next/navigation", () => ({
      useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
      useSearchParams: () => new URLSearchParams(),
      usePathname: () => "/team/coordinator",
    }));
    vi.doMock("../../../lib/hooks", () => ({
      useAgent: vi.fn().mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
      }),
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders loading skeleton when isLoading is true", async () => {
    const { AgentDetailView } = await import("../[slug]/AgentDetailView");
    const { container } = render(<AgentDetailView slug="coordinator" />, { wrapper: makeWrapper() });
    // PageSkeleton variant="detail" renders animate-pulse skeleton elements
    const skeleton = container.querySelector(".animate-pulse");
    expect(skeleton).toBeInTheDocument();
  });
});
