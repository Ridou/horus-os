import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IntegrationCard } from "../../app/integrations/IntegrationCard";
import type { IntegrationStatus } from "../../lib/types";

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

describe("IntegrationCard", () => {
  it("renders integration name and a StatusDot", () => {
    render(
      <IntegrationCard
        integration={mockIntegration}
        onViewWalkthrough={vi.fn()}
      />,
    );
    expect(screen.getByText("Anthropic")).toBeInTheDocument();
    const dot = document.body.querySelector('[role="img"]');
    expect(dot).toBeInTheDocument();
  });

  it("calls onViewWalkthrough on click", async () => {
    const onViewWalkthrough = vi.fn();
    const { container } = render(
      <IntegrationCard
        integration={mockIntegration}
        onViewWalkthrough={onViewWalkthrough}
      />,
    );
    const card = container.querySelector('[role="button"]');
    await userEvent.click(card!);
    expect(onViewWalkthrough).toHaveBeenCalledTimes(1);
  });

  it("calls onViewWalkthrough on Enter key", async () => {
    const onViewWalkthrough = vi.fn();
    const { container } = render(
      <IntegrationCard
        integration={mockIntegration}
        onViewWalkthrough={onViewWalkthrough}
      />,
    );
    const card = container.querySelector('[role="button"]');
    (card as HTMLElement).focus();
    await userEvent.keyboard("{Enter}");
    expect(onViewWalkthrough).toHaveBeenCalledTimes(1);
  });

  it("renders StatusDot with state matching integration.status", () => {
    const configuredIntegration: IntegrationStatus = {
      ...mockIntegration,
      status: "configured-unverified",
    };
    const { container } = render(
      <IntegrationCard
        integration={configuredIntegration}
        onViewWalkthrough={vi.fn()}
      />,
    );
    const dot = container.querySelector('[role="img"]');
    expect(dot).toHaveAttribute("aria-label", "Configured, verification pending");
  });
});
