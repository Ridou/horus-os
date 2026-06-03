import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { Task, TasksResponse } from "../../../lib/types";

const demoTasks: Task[] = [
  {
    task_id: "demo-task-pending-001",
    title: "Review the starter team configuration",
    description: "Open the Team page to see the five starter agents and their roles.",
    status: "pending",
    agent_profile_name: "Coordinator",
    created_at: "2026-05-31T10:00:00Z",
    updated_at: "2026-05-31T10:00:00Z",
  },
  {
    task_id: "demo-task-running-001",
    title: "Analyze codebase structure",
    description: "Scanning source files and building a dependency map.",
    status: "running",
    agent_profile_name: "Engineer",
    created_at: "2026-05-31T10:01:00Z",
    updated_at: "2026-05-31T10:01:00Z",
  },
  {
    task_id: "demo-task-completed-001",
    title: "Generate project overview note",
    description: "Written a summary of the project to notes/project-overview.md.",
    status: "completed",
    agent_profile_name: "Writer",
    created_at: "2026-05-31T09:55:00Z",
    updated_at: "2026-05-31T09:56:00Z",
  },
  {
    task_id: "demo-task-error-001",
    title: "Fetch external documentation",
    description: "Connection to remote host timed out. Retry when network is available.",
    status: "error",
    agent_profile_name: "Researcher",
    created_at: "2026-05-31T09:50:00Z",
    updated_at: "2026-05-31T09:51:00Z",
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

describe("TasksPage (live data)", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.doMock("next/navigation", () => ({
      useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
      useSearchParams: () => new URLSearchParams(),
      usePathname: () => "/tasks",
    }));
    vi.doMock("../../../lib/hooks", () => ({
      useTasks: vi.fn().mockReturnValue({
        data: { tasks: demoTasks } as TasksResponse,
        isLoading: false,
        isError: false,
      }),
    }));
    vi.doMock("../../../lib/api", () => ({
      isDemoMode: false,
      api: {
        deleteTask: vi.fn().mockResolvedValue(undefined),
      },
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the page heading", async () => {
    const TasksPage = (await import("../page")).default;
    render(<TasksPage />, { wrapper: makeWrapper() });
    expect(screen.getByRole("heading", { name: /tasks/i })).toBeInTheDocument();
  });

  it("renders seeded task rows from fixture fallback", async () => {
    const TasksPage = (await import("../page")).default;
    render(<TasksPage />, { wrapper: makeWrapper() });
    expect(screen.getByText("Review the starter team configuration")).toBeInTheDocument();
    expect(screen.getByText("Analyze codebase structure")).toBeInTheDocument();
    expect(screen.getByText("Generate project overview note")).toBeInTheDocument();
    expect(screen.getByText("Fetch external documentation")).toBeInTheDocument();
  });

  it("shows filter tabs for all statuses", async () => {
    const TasksPage = (await import("../page")).default;
    render(<TasksPage />, { wrapper: makeWrapper() });
    expect(screen.getByRole("button", { name: /^All/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Pending/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Running/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Completed/ })).toBeInTheDocument();
  });

  it("shows Cancel task button for pending/running tasks", async () => {
    const TasksPage = (await import("../page")).default;
    render(<TasksPage />, { wrapper: makeWrapper() });
    // pending + running = 2 cancel buttons
    const cancelButtons = screen.getAllByRole("button", { name: "Cancel task" });
    expect(cancelButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("shows Retry button for error/completed tasks", async () => {
    const TasksPage = (await import("../page")).default;
    render(<TasksPage />, { wrapper: makeWrapper() });
    // error + completed = 2 retry buttons
    const retryButtons = screen.getAllByRole("button", { name: "Retry" });
    expect(retryButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("shows inline cancel confirm row when Cancel task is clicked", async () => {
    const TasksPage = (await import("../page")).default;
    render(<TasksPage />, { wrapper: makeWrapper() });

    const cancelButtons = screen.getAllByRole("button", { name: "Cancel task" });
    await userEvent.click(cancelButtons[0]);

    expect(screen.getByText("Cancel this task?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yes, cancel" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Never mind" })).toBeInTheDocument();
  });

  it("hides inline cancel confirm row when Never mind is clicked", async () => {
    const TasksPage = (await import("../page")).default;
    render(<TasksPage />, { wrapper: makeWrapper() });

    const cancelButtons = screen.getAllByRole("button", { name: "Cancel task" });
    await userEvent.click(cancelButtons[0]);
    expect(screen.getByText("Cancel this task?")).toBeInTheDocument();

    const neverMind = screen.getByRole("button", { name: "Never mind" });
    await userEvent.click(neverMind);
    expect(screen.queryByText("Cancel this task?")).not.toBeInTheDocument();
  });

  it("calls api.deleteTask when Yes, cancel is confirmed", async () => {
    // Re-use the module mocks already registered in beforeEach.
    // Importing the mocked api module gives us a reference to the same vi.fn()
    // that TasksPage will call, without a second vi.resetModules() that would
    // break the shared react-query context between the wrapper and the component.
    const TasksPage = (await import("../page")).default;
    const { api: mockedApi } = await import("../../../lib/api");
    const mockDeleteTask = vi.mocked(mockedApi.deleteTask);
    mockDeleteTask.mockResolvedValue(undefined);

    render(<TasksPage />, { wrapper: makeWrapper() });

    const cancelButtons = screen.getAllByRole("button", { name: "Cancel task" });
    await userEvent.click(cancelButtons[0]);

    const confirmButton = screen.getByRole("button", { name: "Yes, cancel" });
    await userEvent.click(confirmButton);

    await waitFor(() => {
      expect(mockDeleteTask).toHaveBeenCalledTimes(1);
    });
  });
});

describe("TasksPage (empty state)", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.doMock("next/navigation", () => ({
      useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
      useSearchParams: () => new URLSearchParams(),
      usePathname: () => "/tasks",
    }));
    vi.doMock("../../../lib/hooks", () => ({
      useTasks: vi.fn().mockReturnValue({
        data: { tasks: [] } as TasksResponse,
        isLoading: false,
        isError: false,
      }),
    }));
    vi.doMock("../../../lib/api", () => ({
      isDemoMode: false,
      api: { deleteTask: vi.fn() },
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders empty state when task list is empty", async () => {
    const TasksPage = (await import("../page")).default;
    render(<TasksPage />, { wrapper: makeWrapper() });
    expect(screen.getByText("No tasks yet")).toBeInTheDocument();
  });
});

describe("TasksPage (error state)", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.doMock("next/navigation", () => ({
      useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
      useSearchParams: () => new URLSearchParams(),
      usePathname: () => "/tasks",
    }));
    vi.doMock("../../../lib/hooks", () => ({
      useTasks: vi.fn().mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
      }),
    }));
    vi.doMock("../../../lib/api", () => ({
      isDemoMode: false,
      api: { deleteTask: vi.fn() },
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders error state when query fails", async () => {
    const TasksPage = (await import("../page")).default;
    render(<TasksPage />, { wrapper: makeWrapper() });
    expect(screen.getByText("Could not load tasks")).toBeInTheDocument();
  });
});
