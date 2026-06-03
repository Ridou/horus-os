import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Modal } from "../Modal";

describe("Modal", () => {
  it("renders dialog and title when open=true", () => {
    render(
      <Modal open={true} onOpenChange={vi.fn()} title="Test Title">
        <p>Content</p>
      </Modal>,
    );
    expect(
      document.body.querySelector('[role="dialog"]'),
    ).toBeInTheDocument();
    expect(screen.getByText("Test Title")).toBeInTheDocument();
  });

  it("calls onOpenChange(false) when Escape is pressed", async () => {
    const onOpenChange = vi.fn();
    render(
      <Modal open={true} onOpenChange={onOpenChange} title="Escape Test">
        <p>Content</p>
      </Modal>,
    );
    await userEvent.keyboard("{Escape}");
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("does not mount dialog when open=false", () => {
    render(
      <Modal open={false} onOpenChange={vi.fn()} title="Closed Modal">
        <p>Hidden</p>
      </Modal>,
    );
    expect(
      document.body.querySelector('[role="dialog"]'),
    ).not.toBeInTheDocument();
  });

  it("portals the dialog to document.body, not the render container", () => {
    const { container } = render(
      <Modal open={true} onOpenChange={vi.fn()} title="Portal Test">
        <p>Content</p>
      </Modal>,
    );
    // Dialog must NOT be inside the render container
    expect(
      container.querySelector('[role="dialog"]'),
    ).not.toBeInTheDocument();
    // Dialog must be in document.body
    expect(
      document.body.querySelector('[role="dialog"]'),
    ).toBeInTheDocument();
  });

  it("close button has aria-label Close", () => {
    render(
      <Modal open={true} onOpenChange={vi.fn()} title="Close Button Test">
        <p>Content</p>
      </Modal>,
    );
    const closeBtn = document.body.querySelector('[aria-label="Close"]');
    expect(closeBtn).toBeInTheDocument();
  });
});
