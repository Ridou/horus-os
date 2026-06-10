import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// Mock next/navigation to control usePathname
vi.mock("next/navigation", () => ({
  usePathname: vi.fn(() => "/"),
}));

// Mock next/image to avoid jsdom issues
vi.mock("next/image", () => ({
  default: (props: Record<string, unknown>) => {
    const { src, alt, width, height, priority, ...rest } = props;
    return <img src={src as string} alt={alt as string} width={width as number} height={height as number} {...rest} />;
  },
}));

// Mock next/link as a plain anchor
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

import { Sidebar } from "../Sidebar";

const { usePathname } = await import("next/navigation") as { usePathname: ReturnType<typeof vi.fn> };

describe("Sidebar", () => {
  it("renders exactly 14 nav links with the locked labels and no Get started", () => {
    (usePathname as ReturnType<typeof vi.fn>).mockReturnValue("/");
    render(<Sidebar />);

    const expectedLabels = [
      "Home",
      "Chat",
      "Team",
      "Store",
      "Memory",
      "Tasks",
      "Research",
      "Activity",
      "Standup",
      "Traces",
      "Costs",
      "Integrations",
      "Settings",
      "About",
    ];

    // All expected nav links are present
    for (const label of expectedLabels) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }

    // Get started must NOT appear
    expect(screen.queryByText("Get started")).not.toBeInTheDocument();

    // Exactly 13 nav links (anchors inside <nav>)
    const nav = document.querySelector("nav");
    expect(nav).toBeInTheDocument();
    const navLinks = nav!.querySelectorAll("a");
    expect(navLinks).toHaveLength(14);
  });

  it("marks the Integrations link as active when pathname is /integrations", () => {
    (usePathname as ReturnType<typeof vi.fn>).mockReturnValue("/integrations");
    render(<Sidebar />);

    const integrationsLink = screen.getByText("Integrations").closest("a");
    expect(integrationsLink).toHaveAttribute("aria-current", "page");
    expect(integrationsLink).toHaveClass("bg-accent-cyan/10");
    expect(integrationsLink).toHaveClass("text-accent-cyan");

    const homeLink = screen.getByText("Home").closest("a");
    expect(homeLink).not.toHaveAttribute("aria-current", "page");
  });

  it("marks the Team link as the only active link when pathname is /team", () => {
    (usePathname as ReturnType<typeof vi.fn>).mockReturnValue("/team");
    render(<Sidebar />);

    const teamLink = screen.getByText("Team").closest("a");
    expect(teamLink).toHaveAttribute("aria-current", "page");
    expect(teamLink).toHaveClass("bg-accent-cyan/10");
    expect(teamLink).toHaveClass("text-accent-cyan");

    // All other nav links must NOT be active
    const nav = document.querySelector("nav");
    const activeLinks = nav!.querySelectorAll("[aria-current='page']");
    expect(activeLinks).toHaveLength(1);
  });
});
