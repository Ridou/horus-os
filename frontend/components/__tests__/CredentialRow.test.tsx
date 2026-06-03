import {
  describe,
  it,
  expect,
  vi,
  beforeEach,
  afterEach,
} from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { IntegrationStatus } from "../../lib/types";

const mockIntegration: IntegrationStatus = {
  id: "anthropic",
  name: "Anthropic",
  category: "AI Provider",
  description: "Powers the default agent runtime.",
  status: "configured-unverified",
  env_var: "ANTHROPIC_API_KEY",
  required_vars: ["ANTHROPIC_API_KEY"],
  credential_portal_url: "https://console.anthropic.com/settings/keys",
};

const missingIntegration: IntegrationStatus = {
  ...mockIntegration,
  status: "missing",
};

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("CredentialRow (live mode)", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.doMock("../../lib/api", () => ({
      isDemoMode: false,
      api: {
        saveCredential: vi.fn().mockResolvedValue({ ok: true }),
        verifyIntegration: vi.fn().mockResolvedValue({ ok: true }),
      },
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders 8-bullet masked value when status is not missing and no injected secret appears", async () => {
    const { CredentialRow } = await import(
      "../../app/settings/CredentialRow"
    );
    const secret = "sk-ant-supersecret-should-never-appear";
    render(
      <CredentialRow
        integration={{ ...mockIntegration, status: "configured-unverified" }}
        onRestartRequired={vi.fn()}
      />,
      { wrapper: makeWrapper() },
    );
    expect(screen.getByText("••••••••")).toBeInTheDocument();
    expect(screen.queryByText(secret)).not.toBeInTheDocument();
  });

  it("renders 'Not set' when status is missing", async () => {
    const { CredentialRow } = await import(
      "../../app/settings/CredentialRow"
    );
    render(
      <CredentialRow
        integration={missingIntegration}
        onRestartRequired={vi.fn()}
      />,
      { wrapper: makeWrapper() },
    );
    expect(screen.getByText("Not set")).toBeInTheDocument();
    expect(screen.queryByText("••••••••")).not.toBeInTheDocument();
  });

  it("shows Replace button and Verify now button in live mode when status is not missing", async () => {
    const { CredentialRow } = await import(
      "../../app/settings/CredentialRow"
    );
    render(
      <CredentialRow
        integration={mockIntegration}
        onRestartRequired={vi.fn()}
      />,
      { wrapper: makeWrapper() },
    );
    expect(screen.getByRole("button", { name: /Replace ANTHROPIC_API_KEY/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Verify Anthropic/i })).toBeInTheDocument();
  });

  it("successful save reflects configured-unverified, clears input, and invokes restart callback", async () => {
    const { CredentialRow } = await import(
      "../../app/settings/CredentialRow"
    );
    const onRestartRequired = vi.fn();
    render(
      <CredentialRow
        integration={mockIntegration}
        onRestartRequired={onRestartRequired}
      />,
      { wrapper: makeWrapper() },
    );

    // Open the replace form
    const replaceBtn = screen.getByRole("button", {
      name: /Replace ANTHROPIC_API_KEY/i,
    });
    await userEvent.click(replaceBtn);

    // Type into the password input
    const input = screen.getByPlaceholderText("Paste new value...");
    await userEvent.type(input, "new-secret-value");

    // Click Save credential
    const saveBtn = screen.getByRole("button", { name: "Save credential" });
    await userEvent.click(saveBtn);

    // After save success: restart callback called, form closes, status reflects configured-unverified
    await waitFor(() => {
      expect(onRestartRequired).toHaveBeenCalledTimes(1);
    });
    // Form should be closed (input no longer visible)
    expect(screen.queryByPlaceholderText("Paste new value...")).not.toBeInTheDocument();
    // Status label reflects configured-unverified
    expect(screen.getByText("Configured, not verified")).toBeInTheDocument();
  });

  it("clears stale verifyError when a new save succeeds (IN-03)", async () => {
    // Arrange: verifyIntegration fails, then saveCredential succeeds.
    vi.resetModules();
    vi.doMock("../../lib/api", () => ({
      isDemoMode: false,
      api: {
        saveCredential: vi.fn().mockResolvedValue({ ok: true }),
        verifyIntegration: vi.fn().mockResolvedValue({ ok: false }),
      },
    }));
    const { CredentialRow } = await import(
      "../../app/settings/CredentialRow"
    );
    render(
      <CredentialRow
        integration={mockIntegration}
        onRestartRequired={vi.fn()}
      />,
      { wrapper: makeWrapper() },
    );

    // Trigger a failed verification so verifyError banner appears.
    const verifyBtn = screen.getByRole("button", { name: /Verify Anthropic/i });
    await userEvent.click(verifyBtn);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(screen.getByRole("alert").textContent).toMatch(/Verification failed/);

    // Open replace form, type a value, and save.
    const replaceBtn = screen.getByRole("button", {
      name: /Replace ANTHROPIC_API_KEY/i,
    });
    await userEvent.click(replaceBtn);
    const input = screen.getByPlaceholderText("Paste new value...");
    await userEvent.type(input, "sk-new-key");
    const saveBtn = screen.getByRole("button", { name: "Save credential" });
    await userEvent.click(saveBtn);

    // After successful save the verifyError banner must be gone.
    await waitFor(() => {
      expect(
        screen.queryByText(/Verification failed/),
      ).not.toBeInTheDocument();
    });
  });

  it("clears stale verifyError when Replace button is clicked (IN-03)", async () => {
    vi.resetModules();
    vi.doMock("../../lib/api", () => ({
      isDemoMode: false,
      api: {
        saveCredential: vi.fn().mockResolvedValue({ ok: true }),
        verifyIntegration: vi.fn().mockResolvedValue({ ok: false }),
      },
    }));
    const { CredentialRow } = await import(
      "../../app/settings/CredentialRow"
    );
    render(
      <CredentialRow
        integration={mockIntegration}
        onRestartRequired={vi.fn()}
      />,
      { wrapper: makeWrapper() },
    );

    // Trigger failed verification to set verifyError.
    const verifyBtn = screen.getByRole("button", { name: /Verify Anthropic/i });
    await userEvent.click(verifyBtn);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });

    // Opening the Replace form should clear the verify error banner.
    const replaceBtn = screen.getByRole("button", {
      name: /Replace ANTHROPIC_API_KEY/i,
    });
    await userEvent.click(replaceBtn);

    expect(
      screen.queryByText(/Verification failed/),
    ).not.toBeInTheDocument();
  });
});

describe("CredentialRow (demo mode)", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.doMock("../../lib/api", () => ({
      isDemoMode: true,
      api: {
        saveCredential: vi.fn(),
        verifyIntegration: vi.fn(),
      },
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("hides Replace form trigger and Verify now button in demo mode", async () => {
    const { CredentialRow } = await import(
      "../../app/settings/CredentialRow"
    );
    render(
      <CredentialRow
        integration={mockIntegration}
        onRestartRequired={vi.fn()}
      />,
      { wrapper: makeWrapper() },
    );
    // Verify now button must not be in the DOM
    expect(
      screen.queryByRole("button", { name: /Verify Anthropic/i }),
    ).not.toBeInTheDocument();
    // Replace button must not be in the DOM
    expect(
      screen.queryByRole("button", { name: /Replace ANTHROPIC_API_KEY/i }),
    ).not.toBeInTheDocument();
  });

  it("shows demo mode notice copy in demo mode", async () => {
    const { CredentialRow } = await import(
      "../../app/settings/CredentialRow"
    );
    render(
      <CredentialRow
        integration={mockIntegration}
        onRestartRequired={vi.fn()}
      />,
      { wrapper: makeWrapper() },
    );
    expect(
      screen.getByText("Credential management is disabled in demo mode."),
    ).toBeInTheDocument();
  });

  it("still renders StatusDot in demo mode (read-only)", async () => {
    const { CredentialRow } = await import(
      "../../app/settings/CredentialRow"
    );
    render(
      <CredentialRow
        integration={mockIntegration}
        onRestartRequired={vi.fn()}
      />,
      { wrapper: makeWrapper() },
    );
    const dot = document.body.querySelector('[role="img"]');
    expect(dot).toBeInTheDocument();
  });
});
