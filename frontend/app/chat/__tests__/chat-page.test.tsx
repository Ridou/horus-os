import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ChatStreamEvent } from "../../../lib/types";

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

/**
 * Wire the shared module mocks. `events` is the canned SSE stream the mocked
 * chatStream replays into the onEvent callback. `searchQuery` seeds the
 * ?q= deep link.
 */
function mockModules(opts: {
  events?: ChatStreamEvent[];
  searchQuery?: string;
}) {
  vi.resetModules();
  const params = new URLSearchParams(
    opts.searchQuery ? { q: opts.searchQuery } : {},
  );
  vi.doMock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
    useSearchParams: () => params,
    usePathname: () => "/chat",
  }));
  vi.doMock("../../../lib/hooks", () => ({
    useAgents: vi.fn().mockReturnValue({
      data: {
        agents: [
          { name: "Coordinator", default_model: "claude" },
          { name: "Researcher", default_model: "claude" },
        ],
      },
    }),
  }));
  const chatStream = vi.fn(
    async (
      _body: unknown,
      onEvent: (e: ChatStreamEvent) => void,
    ): Promise<void> => {
      for (const e of opts.events ?? []) onEvent(e);
    },
  );
  vi.doMock("../../../lib/api", () => ({
    isDemoMode: false,
    api: { chatStream },
  }));
}

describe("ChatPage", () => {
  beforeEach(() => {
    mockModules({
      events: [
        { type: "token", text: "Hello " },
        { type: "token", text: "there" },
        { type: "done", trace_id: "trace-abc", latency_ms: 12 },
      ],
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the heading, the composer, and the agent picker", async () => {
    const ChatPage = (await import("../page")).default;
    render(<ChatPage />, { wrapper: makeWrapper() });

    expect(
      screen.getByRole("heading", { name: /chat/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/message/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
    // The picker lists the available agents plus a Default option.
    expect(screen.getByLabelText("Agent")).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "Coordinator" }),
    ).toBeInTheDocument();
  });

  it("streams the assistant reply and links to its trace after sending", async () => {
    const ChatPage = (await import("../page")).default;
    const { api: mockedApi } = await import("../../../lib/api");
    render(<ChatPage />, { wrapper: makeWrapper() });

    await userEvent.type(
      screen.getByLabelText(/message/i),
      "What can you do?",
    );
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    // The user turn is echoed and the streamed assistant tokens accumulate.
    await waitFor(() => {
      expect(screen.getByText("What can you do?")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText("Hello there")).toBeInTheDocument();
    });
    // The completed turn links to its generating trace.
    expect(
      screen.getByRole("link", { name: /view trace/i }),
    ).toBeInTheDocument();
    expect(vi.mocked(mockedApi.chatStream)).toHaveBeenCalledTimes(1);
  });
});

describe("ChatPage (deep link)", () => {
  beforeEach(() => {
    mockModules({
      searchQuery: "auto sent prompt",
      events: [
        { type: "token", text: "Answer." },
        { type: "done", trace_id: "trace-xyz", latency_ms: 5 },
      ],
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("auto-sends the ?q= prompt once on mount", async () => {
    const ChatPage = (await import("../page")).default;
    const { api: mockedApi } = await import("../../../lib/api");
    render(<ChatPage />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(screen.getByText("auto sent prompt")).toBeInTheDocument();
    });
    expect(screen.getByText("Answer.")).toBeInTheDocument();
    expect(vi.mocked(mockedApi.chatStream)).toHaveBeenCalledTimes(1);
  });
});
