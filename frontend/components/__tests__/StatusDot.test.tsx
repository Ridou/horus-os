import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { StatusDot } from "../StatusDot";

describe("StatusDot", () => {
  it("renders with role=img and correct aria-label and bg class for verified state", () => {
    const { container } = render(<StatusDot state="verified" />);
    const wrapper = container.querySelector('[role="img"]');
    expect(wrapper).toBeInTheDocument();
    expect(wrapper).toHaveAttribute("aria-label", "Verified");
    // dot element with bg-success
    const dot = container.querySelector(".bg-success");
    expect(dot).toBeInTheDocument();
  });

  it("renders all four states with correct aria-labels and bg classes", () => {
    const cases: Array<{
      state: "verified" | "configured-unverified" | "missing" | "error";
      label: string;
      bgClass: string;
    }> = [
      { state: "verified", label: "Verified", bgClass: "bg-success" },
      {
        state: "configured-unverified",
        label: "Configured, verification pending",
        bgClass: "bg-warning",
      },
      { state: "missing", label: "Not configured", bgClass: "bg-text-muted" },
      {
        state: "error",
        label: "Configuration error",
        bgClass: "bg-danger",
      },
    ];

    for (const { state, label, bgClass } of cases) {
      const { container, unmount } = render(<StatusDot state={state} />);
      const wrapper = container.querySelector('[role="img"]');
      expect(wrapper, `aria-label for ${state}`).toHaveAttribute(
        "aria-label",
        label,
      );
      expect(
        container.querySelector(`.${bgClass}`),
        `bg class for ${state}`,
      ).toBeInTheDocument();
      unmount();
    }
  });

  it("applies status-pulse on inner dot and animate-pulse on outer ring when pulse=true; no status-pulse when pulse omitted", () => {
    // With pulse
    const { container: pulseContainer, unmount: u1 } = render(
      <StatusDot state="verified" pulse={true} />,
    );
    expect(pulseContainer.querySelector(".status-pulse")).toBeInTheDocument();
    expect(
      pulseContainer.querySelector(".animate-pulse"),
    ).toBeInTheDocument();
    u1();

    // Without pulse
    const { container: staticContainer } = render(
      <StatusDot state="verified" />,
    );
    expect(
      staticContainer.querySelector(".status-pulse"),
    ).not.toBeInTheDocument();
  });

  it("overrides aria-label with label prop", () => {
    const { container } = render(
      <StatusDot state="missing" label="Custom label" />,
    );
    const wrapper = container.querySelector('[role="img"]');
    expect(wrapper).toHaveAttribute("aria-label", "Custom label");
  });
});
