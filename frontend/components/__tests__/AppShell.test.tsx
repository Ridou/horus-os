import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

// Control usePathname so the route-change effect stays inert during a test.
vi.mock("next/navigation", () => ({
  usePathname: vi.fn(() => "/"),
}));

// Render next/image as a plain img to avoid jsdom loader issues.
vi.mock("next/image", () => ({
  default: (props: Record<string, unknown>) => {
    const { src, alt, width, height, priority, ...rest } = props;
    return (
      <img
        src={src as string}
        alt={alt as string}
        width={width as number}
        height={height as number}
        {...rest}
      />
    );
  },
}));

// Render next/link as a plain anchor.
vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

// Keep the demo banner out of the way; the drawer behavior is independent of it.
vi.mock("@/lib/api", () => ({ isDemoMode: false }));

import { AppShell } from "../AppShell";

function getSidebar() {
  return document.getElementById("app-sidebar");
}

describe("AppShell mobile navigation", () => {
  it("opens and closes the drawer via the hamburger, close button, and Escape", () => {
    render(
      <AppShell>
        <div>content</div>
      </AppShell>,
    );

    const openButton = screen.getByRole("button", {
      name: "Open navigation menu",
    });
    expect(openButton).toHaveAttribute("aria-expanded", "false");
    expect(openButton).toHaveAttribute("aria-controls", "app-sidebar");

    // Hidden off-canvas to start.
    expect(getSidebar()).toHaveClass("-translate-x-full");

    // Hamburger opens it.
    fireEvent.click(openButton);
    expect(openButton).toHaveAttribute("aria-expanded", "true");
    expect(getSidebar()).toHaveClass("translate-x-0");

    // The in-drawer close button dismisses it.
    fireEvent.click(
      screen.getByRole("button", { name: "Close navigation menu" }),
    );
    expect(
      screen.getByRole("button", { name: "Open navigation menu" }),
    ).toHaveAttribute("aria-expanded", "false");
    expect(getSidebar()).toHaveClass("-translate-x-full");

    // Reopen, then Escape closes it.
    fireEvent.click(
      screen.getByRole("button", { name: "Open navigation menu" }),
    );
    expect(getSidebar()).toHaveClass("translate-x-0");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(getSidebar()).toHaveClass("-translate-x-full");
  });

  it("marks the closed drawer inert on mobile and clears it once open", () => {
    render(
      <AppShell>
        <div>content</div>
      </AppShell>,
    );

    // jsdom has no matchMedia, so useIsDesktop resolves to false (mobile):
    // a closed drawer must be inert and hidden from assistive tech.
    expect(getSidebar()).toHaveAttribute("inert");
    expect(getSidebar()).toHaveAttribute("aria-hidden", "true");

    fireEvent.click(
      screen.getByRole("button", { name: "Open navigation menu" }),
    );
    expect(getSidebar()).not.toHaveAttribute("inert");
    expect(getSidebar()).not.toHaveAttribute("aria-hidden");
  });

  it("closes the drawer when a nav link is activated", () => {
    render(
      <AppShell>
        <div>content</div>
      </AppShell>,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Open navigation menu" }),
    );
    expect(getSidebar()).toHaveClass("translate-x-0");

    fireEvent.click(screen.getByRole("link", { name: /Team/i }));
    expect(getSidebar()).toHaveClass("-translate-x-full");
  });

  it("locks body scroll while the drawer is open and restores it on close", () => {
    render(
      <AppShell>
        <div>content</div>
      </AppShell>,
    );

    expect(document.body.style.overflow).toBe("");

    fireEvent.click(
      screen.getByRole("button", { name: "Open navigation menu" }),
    );
    expect(document.body.style.overflow).toBe("hidden");

    fireEvent.keyDown(document, { key: "Escape" });
    expect(document.body.style.overflow).toBe("");
  });
});
