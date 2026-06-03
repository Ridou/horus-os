import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ExampleDataBanner } from "../ExampleDataBanner";

describe("ExampleDataBanner", () => {
  it("renders the Example data heading and body text", () => {
    render(<ExampleDataBanner />);
    expect(screen.getByText("Example data")).toBeInTheDocument();
    expect(
      screen.getByText(
        "This content was seeded automatically and is safe to clear.",
      ),
    ).toBeInTheDocument();
  });

  it("renders dismiss X button with aria-label when showClear is false", () => {
    const onDismiss = vi.fn();
    render(<ExampleDataBanner showClear={false} onDismiss={onDismiss} />);

    const dismissBtn = screen.getByRole("button", {
      name: "Dismiss example data banner",
    });
    expect(dismissBtn).toBeInTheDocument();

    fireEvent.click(dismissBtn);
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it("renders Clear demo data button when showClear is true", () => {
    render(<ExampleDataBanner showClear={true} />);
    expect(
      screen.getByRole("button", { name: "Clear demo data" }),
    ).toBeInTheDocument();
    // no dismiss X when showClear is true
    expect(
      screen.queryByRole("button", { name: "Dismiss example data banner" }),
    ).not.toBeInTheDocument();
  });

  it("clicking Clear demo data reveals the inline confirm row", () => {
    render(<ExampleDataBanner showClear={true} />);

    expect(
      screen.queryByText("This will permanently delete the demo trace. Are you sure?"),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Clear demo data" }));

    expect(
      screen.getByText("This will permanently delete the demo trace. Are you sure?"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Delete demo trace" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Keep it" }),
    ).toBeInTheDocument();
  });

  it("clicking Keep it cancels the confirm row", () => {
    render(<ExampleDataBanner showClear={true} />);

    fireEvent.click(screen.getByRole("button", { name: "Clear demo data" }));
    expect(
      screen.getByText("This will permanently delete the demo trace. Are you sure?"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Keep it" }));
    expect(
      screen.queryByText("This will permanently delete the demo trace. Are you sure?"),
    ).not.toBeInTheDocument();
  });

  it("clicking Delete demo trace calls onClear", async () => {
    const onClear = vi.fn().mockResolvedValue(undefined);
    render(<ExampleDataBanner showClear={true} onClear={onClear} />);

    fireEvent.click(screen.getByRole("button", { name: "Clear demo data" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete demo trace" }));

    await waitFor(() => expect(onClear).toHaveBeenCalledOnce());
    // confirm row hidden after success
    expect(
      screen.queryByText("This will permanently delete the demo trace. Are you sure?"),
    ).not.toBeInTheDocument();
  });

  it("shows inline error copy when onClear throws", async () => {
    const onClear = vi.fn().mockRejectedValue(new Error("network error"));
    render(<ExampleDataBanner showClear={true} onClear={onClear} />);

    fireEvent.click(screen.getByRole("button", { name: "Clear demo data" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete demo trace" }));

    await waitFor(() =>
      expect(
        screen.getByText("Could not clear demo data. Try again."),
      ).toBeInTheDocument(),
    );
  });
});
