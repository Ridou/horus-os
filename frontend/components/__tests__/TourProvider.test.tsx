import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { TourProvider, useTour } from "../TourProvider";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: vi.fn() })),
  usePathname: vi.fn(() => "/"),
}));

/** Helper component that exposes the useTour context values as data attributes. */
function TourConsumer() {
  const { isTourActive, currentStep, totalSteps, startTour, skipTour } =
    useTour();
  return (
    <div
      data-testid="consumer"
      data-active={String(isTourActive)}
      data-step={currentStep}
      data-total={totalSteps}
    >
      <button type="button" onClick={startTour} data-testid="start">
        start
      </button>
      <button type="button" onClick={skipTour} data-testid="skip">
        skip
      </button>
    </div>
  );
}

const TOUR_KEY = "horus_tour_completed";

describe("TourProvider", () => {
  beforeEach(() => {
    // Reset localStorage between tests
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("auto-starts the tour when horus_tour_completed is absent", async () => {
    render(
      <TourProvider>
        <TourConsumer />
      </TourProvider>,
    );

    // After useEffect fires, isTourActive becomes true
    await act(async () => {});

    const consumer = screen.getByTestId("consumer");
    expect(consumer.dataset.active).toBe("true");
  });

  it("does NOT auto-start when horus_tour_completed is set", async () => {
    localStorage.setItem(TOUR_KEY, "1");

    render(
      <TourProvider>
        <TourConsumer />
      </TourProvider>,
    );

    await act(async () => {});

    const consumer = screen.getByTestId("consumer");
    expect(consumer.dataset.active).toBe("false");
  });

  it("skipTour sets horus_tour_completed and deactivates the tour", async () => {
    render(
      <TourProvider>
        <TourConsumer />
      </TourProvider>,
    );

    await act(async () => {});
    // tour should be active now
    expect(screen.getByTestId("consumer").dataset.active).toBe("true");

    await act(async () => {
      screen.getByTestId("skip").click();
    });

    expect(localStorage.getItem(TOUR_KEY)).toBe("1");
    expect(screen.getByTestId("consumer").dataset.active).toBe("false");
  });

  it("startTour removes the completed flag, resets step to 0, and activates tour", async () => {
    localStorage.setItem(TOUR_KEY, "1");

    render(
      <TourProvider>
        <TourConsumer />
      </TourProvider>,
    );

    await act(async () => {});
    expect(screen.getByTestId("consumer").dataset.active).toBe("false");

    await act(async () => {
      screen.getByTestId("start").click();
    });

    expect(localStorage.getItem(TOUR_KEY)).toBeNull();
    expect(screen.getByTestId("consumer").dataset.active).toBe("true");
    expect(screen.getByTestId("consumer").dataset.step).toBe("0");
  });

  it("exposes totalSteps equal to 5 (TOUR_STEPS constant)", async () => {
    render(
      <TourProvider>
        <TourConsumer />
      </TourProvider>,
    );

    await act(async () => {});

    const consumer = screen.getByTestId("consumer");
    expect(consumer.dataset.total).toBe("5");
  });

  it("useTour throws when called outside TourProvider", () => {
    // Suppress the expected React error boundary console.error
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    function Standalone() {
      useTour();
      return null;
    }
    expect(() => render(<Standalone />)).toThrow(
      "useTour must be used inside TourProvider",
    );
    spy.mockRestore();
  });
});
