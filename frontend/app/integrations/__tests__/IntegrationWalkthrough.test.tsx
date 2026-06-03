import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { IntegrationStatus } from "../../../lib/types";

const mockIntegration: IntegrationStatus = {
  id: "anthropic",
  name: "Anthropic",
  category: "AI Provider",
  description: "Powers the default agent runtime.",
  status: "missing",
  env_var: "ANTHROPIC_API_KEY",
  required_vars: ["ANTHROPIC_API_KEY"],
  credential_portal_url: "https://console.anthropic.com/settings/keys",
};

describe("IntegrationWalkthrough (live mode)", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.doMock("../../../lib/api", () => ({ isDemoMode: false }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders modal title and integration name when open=true", async () => {
    const { IntegrationWalkthrough } = await import("../IntegrationWalkthrough");
    render(
      <IntegrationWalkthrough
        integration={mockIntegration}
        open={true}
        onClose={vi.fn()}
        currentStep={0}
        onStepChange={vi.fn()}
      />,
    );
    expect(document.body.querySelector('[role="dialog"]')).toBeInTheDocument();
    expect(screen.getByText("Anthropic")).toBeInTheDocument();
  });

  it("advancing the Stepper changes the visible step", async () => {
    const onStepChange = vi.fn();
    const { IntegrationWalkthrough } = await import("../IntegrationWalkthrough");
    render(
      <IntegrationWalkthrough
        integration={mockIntegration}
        open={true}
        onClose={vi.fn()}
        currentStep={0}
        onStepChange={onStepChange}
      />,
    );
    const continueBtn = screen.getByRole("button", { name: /continue/i });
    await userEvent.click(continueBtn);
    expect(onStepChange).toHaveBeenCalledWith(1);
  });
});

describe("IntegrationWalkthrough (demo mode)", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.doMock("../../../lib/api", () => ({ isDemoMode: true }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows DemoModeNotice and no Continue button in demo mode", async () => {
    const { IntegrationWalkthrough } = await import("../IntegrationWalkthrough");
    render(
      <IntegrationWalkthrough
        integration={mockIntegration}
        open={true}
        onClose={vi.fn()}
        currentStep={0}
        onStepChange={vi.fn()}
      />,
    );
    expect(screen.getByText(/view-only in demo mode/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /continue/i }),
    ).not.toBeInTheDocument();
  });

  it("shows step indicator and Next button in demo mode on step 0", async () => {
    const { IntegrationWalkthrough } = await import("../IntegrationWalkthrough");
    render(
      <IntegrationWalkthrough
        integration={mockIntegration}
        open={true}
        onClose={vi.fn()}
        currentStep={0}
        onStepChange={vi.fn()}
      />,
    );
    expect(screen.getByText(/step 1 of 3/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /next/i })).toBeInTheDocument();
  });

  it("Next navigation in demo mode calls onStepChange to advance steps", async () => {
    const onStepChange = vi.fn();
    const { IntegrationWalkthrough } = await import("../IntegrationWalkthrough");
    render(
      <IntegrationWalkthrough
        integration={mockIntegration}
        open={true}
        onClose={vi.fn()}
        currentStep={0}
        onStepChange={onStepChange}
      />,
    );
    const nextBtn = screen.getByRole("button", { name: /next/i });
    await userEvent.click(nextBtn);
    expect(onStepChange).toHaveBeenCalledWith(1);
  });

  it("demo mode navigation reaches the env-var step (step 3)", async () => {
    const onStepChange = vi.fn();
    const { IntegrationWalkthrough } = await import("../IntegrationWalkthrough");
    const { rerender } = render(
      <IntegrationWalkthrough
        integration={mockIntegration}
        open={true}
        onClose={vi.fn()}
        currentStep={0}
        onStepChange={onStepChange}
      />,
    );
    // Advance to step 2 (env-var step, index 2)
    const nextBtn = screen.getByRole("button", { name: /next/i });
    await userEvent.click(nextBtn);
    expect(onStepChange).toHaveBeenCalledWith(1);

    // Re-render with currentStep=2 to simulate the parent updating state
    rerender(
      <IntegrationWalkthrough
        integration={mockIntegration}
        open={true}
        onClose={vi.fn()}
        currentStep={2}
        onStepChange={onStepChange}
      />,
    );
    expect(screen.getByText(/add to your environment/i)).toBeInTheDocument();
    expect(screen.getByText(/step 3 of 3/i)).toBeInTheDocument();
  });
});
