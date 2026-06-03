import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type {
  ResearchProgress,
  ResearchReport,
  ResearchStartResponse,
} from "../../../lib/types";

const demoPlan: ResearchStartResponse = {
  task_id: "demo-research-001",
  trace_id: "demo-trace-research-001",
  status: "pending",
  plan: {
    question: "What are the tradeoffs of running local LLMs?",
    subtopics: [
      {
        title: "Hardware and memory requirements",
        query: "local LLM hardware VRAM quantization",
      },
      {
        title: "Latency versus hosted APIs",
        query: "local LLM latency throughput compared to hosted API",
      },
    ],
  },
};

const demoReport: ResearchReport = {
  task_id: "demo-research-001",
  trace_id: "demo-trace-research-001",
  report:
    "# Local LLM tradeoffs\n\n## Hardware\n\nA 7B model fits consumer hardware once quantized [1].\n\n## References\n\n1. Quantization formats - https://example.test/quantization (fetched 2026-05-31T09:00:00Z)\n",
};

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

/** Set up the shared module mocks. Hook return values are overridable per test. */
function mockModules(opts: {
  progress?: ResearchProgress;
  report?: ResearchReport;
}) {
  vi.resetModules();
  vi.doMock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
    useSearchParams: () => new URLSearchParams(),
    usePathname: () => "/research",
  }));
  vi.doMock("../../../lib/hooks", () => ({
    useResearchProgress: vi.fn().mockReturnValue({ data: opts.progress }),
    useResearchReport: vi.fn().mockReturnValue({ data: opts.report }),
  }));
  vi.doMock("../../../lib/api", () => ({
    isDemoMode: false,
    api: {
      startResearch: vi.fn().mockResolvedValue(demoPlan),
      startResearchRun: vi.fn().mockResolvedValue({ status: "running" }),
      cancelResearch: vi.fn().mockResolvedValue(undefined),
    },
  }));
}

describe("ResearchPage", () => {
  beforeEach(() => {
    mockModules({});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the page heading and the question entry form", async () => {
    const ResearchPage = (await import("../page")).default;
    render(<ResearchPage />, { wrapper: makeWrapper() });
    expect(
      screen.getByRole("heading", { name: /research/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/what are the tradeoffs/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /plan research/i }),
    ).toBeInTheDocument();
  });

  it("shows the plan with Start and Cancel controls BEFORE any execution", async () => {
    const ResearchPage = (await import("../page")).default;
    const { api: mockedApi } = await import("../../../lib/api");
    render(<ResearchPage />, { wrapper: makeWrapper() });

    const textarea = screen.getByPlaceholderText(/what are the tradeoffs/i);
    await userEvent.type(textarea, "What are the tradeoffs of local LLMs?");
    await userEvent.click(
      screen.getByRole("button", { name: /plan research/i }),
    );

    await waitFor(() => {
      expect(
        screen.getByText("Hardware and memory requirements"),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("Latency versus hosted APIs")).toBeInTheDocument();
    // Plan-before-execute: the run has NOT started yet.
    expect(vi.mocked(mockedApi.startResearchRun)).not.toHaveBeenCalled();
    // Both an explicit Start and a Cancel control are present.
    expect(
      screen.getByRole("button", { name: /start research/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^cancel$/i })).toBeInTheDocument();
  });

  it("starts the run only when Start research is clicked", async () => {
    const ResearchPage = (await import("../page")).default;
    const { api: mockedApi } = await import("../../../lib/api");
    render(<ResearchPage />, { wrapper: makeWrapper() });

    await userEvent.type(
      screen.getByPlaceholderText(/what are the tradeoffs/i),
      "Local LLM tradeoffs?",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /plan research/i }),
    );
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /start research/i }),
      ).toBeInTheDocument();
    });
    await userEvent.click(
      screen.getByRole("button", { name: /start research/i }),
    );

    await waitFor(() => {
      expect(vi.mocked(mockedApi.startResearchRun)).toHaveBeenCalledTimes(1);
    });
  });
});

describe("ResearchPage (running)", () => {
  beforeEach(() => {
    mockModules({
      progress: {
        task_id: "demo-research-001",
        phase: "searching",
        sources_found: 4,
        iterations_used: 2,
        iteration_budget: 6,
      },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the live progress panel with phase, sources, and iteration budget", async () => {
    const ResearchPage = (await import("../page")).default;
    render(<ResearchPage />, { wrapper: makeWrapper() });

    await userEvent.type(
      screen.getByPlaceholderText(/what are the tradeoffs/i),
      "Local LLM tradeoffs?",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /plan research/i }),
    );
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /start research/i }),
      ).toBeInTheDocument();
    });
    await userEvent.click(
      screen.getByRole("button", { name: /start research/i }),
    );

    await waitFor(() => {
      expect(screen.getByText("Searching")).toBeInTheDocument();
    });
    expect(screen.getByText("Sources found")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("Iterations")).toBeInTheDocument();
    // iterations_used / iteration_budget
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText(/\/\s*6/)).toBeInTheDocument();
    // The run is inspectable via its trace and visible under tasks (RESEARCH-05).
    expect(screen.getByRole("link", { name: /view trace/i })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /view in tasks/i }),
    ).toBeInTheDocument();
    // A Cancel control is available mid-run (RESEARCH-05).
    expect(
      screen.getByRole("button", { name: /cancel run/i }),
    ).toBeInTheDocument();
  });
});

describe("ResearchPage (completed)", () => {
  beforeEach(() => {
    mockModules({
      progress: {
        task_id: "demo-research-001",
        phase: "done",
        sources_found: 3,
        iterations_used: 6,
        iteration_budget: 6,
      },
      report: demoReport,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the cited report with a citation reference list", async () => {
    const ResearchPage = (await import("../page")).default;
    render(<ResearchPage />, { wrapper: makeWrapper() });

    await userEvent.type(
      screen.getByPlaceholderText(/what are the tradeoffs/i),
      "Local LLM tradeoffs?",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /plan research/i }),
    );
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /start research/i }),
      ).toBeInTheDocument();
    });
    await userEvent.click(
      screen.getByRole("button", { name: /start research/i }),
    );

    // The finished report heading and References section render.
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /local llm tradeoffs/i }),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByRole("heading", { name: /references/i }),
    ).toBeInTheDocument();
    // The reference list URL is rendered as a clickable link.
    expect(
      screen.getByRole("link", { name: /example\.test\/quantization/i }),
    ).toBeInTheDocument();
    // A control links to the generating trace (RESEARCH-05).
    expect(
      screen.getAllByRole("link", { name: /view trace/i }).length,
    ).toBeGreaterThanOrEqual(1);
  });
});
