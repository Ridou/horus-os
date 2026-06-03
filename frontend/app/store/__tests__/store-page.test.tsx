import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { StoreBundle } from "../../../lib/types";

const BUNDLES: StoreBundle[] = [
  {
    slug: "atlas",
    name: "Atlas",
    color: "#38bdf8",
    role: "Travel planner",
    description: "Plans trips and handles travel logistics.",
    default_model: null,
    recommended_tools: ["web_search", "create_note"],
    recommended_adapters: ["calendar"],
    installed: false,
  },
  {
    slug: "sol",
    name: "Sol",
    color: "#f59e0b",
    role: "Reflective companion",
    description: "A reflective conversational companion.",
    default_model: null,
    recommended_tools: ["create_note"],
    recommended_adapters: [],
    installed: true,
  },
];

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

function mockModules() {
  vi.resetModules();
  vi.doMock("../../../lib/hooks", () => ({
    useStoreBundles: vi.fn().mockReturnValue({ data: { bundles: BUNDLES }, isLoading: false }),
  }));
  const installBundle = vi.fn().mockResolvedValue({ name: "Atlas" });
  const createAgent = vi.fn().mockResolvedValue({ name: "Scout" });
  vi.doMock("../../../lib/api", () => ({
    isDemoMode: false,
    api: { installBundle, createAgent },
  }));
}

describe("StorePage (browse)", () => {
  beforeEach(() => {
    mockModules();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("lists featured bundles with install and installed states", async () => {
    const StorePage = (await import("../page")).default;
    render(<StorePage />, { wrapper: makeWrapper() });

    expect(screen.getByRole("heading", { name: /agent store/i })).toBeInTheDocument();
    expect(screen.getByText("Atlas")).toBeInTheDocument();
    expect(screen.getByText("Sol")).toBeInTheDocument();
    // Atlas is installable, Sol is already installed (exact-match the badge so
    // the page description prose, which also says "Installed", is not matched).
    expect(screen.getByRole("button", { name: /^install$/i })).toBeInTheDocument();
    expect(screen.getByText("Installed")).toBeInTheDocument();
  });

  it("installs a bundle when Install is clicked", async () => {
    const StorePage = (await import("../page")).default;
    const { api } = await import("../../../lib/api");
    render(<StorePage />, { wrapper: makeWrapper() });

    await userEvent.click(screen.getByRole("button", { name: /install/i }));
    await waitFor(() => {
      expect(vi.mocked(api.installBundle)).toHaveBeenCalledWith("atlas");
    });
  });
});

describe("StorePage (create)", () => {
  beforeEach(() => {
    mockModules();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("creates a custom agent from the builder form", async () => {
    const StorePage = (await import("../page")).default;
    const { api } = await import("../../../lib/api");
    render(<StorePage />, { wrapper: makeWrapper() });

    await userEvent.click(screen.getByRole("button", { name: /create/i }));
    await userEvent.type(screen.getByLabelText(/name/i), "Scout");
    await userEvent.type(
      screen.getByLabelText(/system prompt/i),
      "You are Scout.",
    );
    await userEvent.type(screen.getByLabelText(/tools/i), "web_search, create_note");
    await userEvent.click(
      screen.getByRole("button", { name: /create agent/i }),
    );

    await waitFor(() => {
      expect(vi.mocked(api.createAgent)).toHaveBeenCalledTimes(1);
    });
    const payload = vi.mocked(api.createAgent).mock.calls[0][0];
    expect(payload.name).toBe("Scout");
    expect(payload.allowed_tools).toEqual(["web_search", "create_note"]);
  });
});
