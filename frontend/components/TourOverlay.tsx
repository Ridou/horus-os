"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { createPortal } from "react-dom";
import { usePathname } from "next/navigation";
import { useTour, TOUR_STEPS } from "./TourProvider";

export function TourOverlay() {
  // SSR guard must come before any hook calls. createPortal requires
  // document.body, which does not exist during server rendering.
  // In a fully static Next.js export this component is always client-only,
  // but the guard ensures the Rules of Hooks are satisfied in any context
  // (test harnesses, future SSR pages) while also preventing a lint warning.
  // We use a mounted flag via useState/useEffect rather than a bare
  // typeof-document check so that all hooks always run unconditionally.
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  const { isTourActive, currentStep, totalSteps, skipTour, nextStep, prevStep } =
    useTour();
  const spotlightRef = useRef<HTMLDivElement>(null);
  const primaryBtnRef = useRef<HTMLButtonElement>(null);
  const pathname = usePathname();
  // Whether the current step's target element was found. When it is, the
  // spotlight box-shadow provides all of the dimming with a crisp cutout so the
  // highlighted area stays fully visible. When it is not (a step whose target
  // is not present on the demo page), fall back to a plain dim so the step card
  // still reads against a backdrop. Either way there is no blur.
  const [hasTarget, setHasTarget] = useState(false);

  // Position the spotlight over the data-tour-step target element.
  // Wait one animation frame after navigation before measuring (Pitfall 2).
  // Also listen for scroll and resize so the spotlight tracks the target
  // when the user scrolls (e.g. Memory page with a long note list) or
  // resizes the browser while the tour is active.
  useEffect(() => {
    if (!isTourActive) return;

    let cancelled = false;
    const timers: number[] = [];
    setHasTarget(false);

    const find = (): boolean => {
      if (cancelled || !spotlightRef.current) return false;
      const el = document.querySelector(
        `[data-tour-step="${currentStep + 1}"]`,
      ) as HTMLElement | null;
      if (!el) {
        // No target on this page: park the spotlight off-screen and let the
        // container fall back to a plain dim.
        Object.assign(spotlightRef.current.style, {
          top: "-9999px",
          left: "-9999px",
          width: "0px",
          height: "0px",
        });
        setHasTarget(false);
        return false;
      }
      const rect = el.getBoundingClientRect();
      const pad = 8;
      Object.assign(spotlightRef.current.style, {
        top: `${rect.top - pad}px`,
        left: `${rect.left - pad}px`,
        width: `${rect.width + pad * 2}px`,
        height: `${rect.height + pad * 2}px`,
      });
      setHasTarget(true);
      return true;
    };

    // The target can mount a frame or two after a route change, so retry
    // briefly before settling on the plain-dim fallback.
    const raf = requestAnimationFrame(() => {
      if (!find()) {
        timers.push(window.setTimeout(find, 120));
        timers.push(window.setTimeout(find, 360));
      }
    });
    window.addEventListener("scroll", find, { passive: true });
    window.addEventListener("resize", find, { passive: true });

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      timers.forEach((t) => window.clearTimeout(t));
      window.removeEventListener("scroll", find);
      window.removeEventListener("resize", find);
    };
  }, [isTourActive, currentStep, pathname]);

  // Move focus to the primary button on each step change so keyboard
  // and screen-reader users are immediately scoped to the dialog.
  useEffect(() => {
    if (isTourActive && primaryBtnRef.current) {
      primaryBtnRef.current.focus();
    }
  }, [isTourActive, currentStep]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") skipTour();
    },
    [skipTour],
  );

  // All hooks have run. Now apply conditional rendering.
  if (!mounted || !isTourActive) return null;

  const step = TOUR_STEPS[currentStep];
  const isLastStep = currentStep === totalSteps - 1;
  const isFirstStep = currentStep === 0;

  return createPortal(
    <div
      className={`fixed inset-0 z-[100] ${hasTarget ? "" : "bg-bg-primary/70"}`}
      tabIndex={-1}
      onKeyDown={handleKeyDown}
    >
      {/* Spotlight ring - portal-mounted, positioned over the target element */}
      <div
        ref={spotlightRef}
        style={{
          position: "fixed",
          top: "-9999px",
          left: "-9999px",
          width: "0px",
          height: "0px",
          boxShadow:
            "0 0 0 9999px rgba(10,11,15,0.75), 0 0 0 2px #00d4ff, 0 0 16px rgba(0,212,255,0.2)",
          borderRadius: "8px",
          transition:
            "top 200ms, left 200ms, width 200ms, height 200ms",
          pointerEvents: "none",
        }}
      />

      {/* Step card */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Onboarding tour, step ${currentStep + 1} of ${totalSteps}`}
        onKeyDown={handleKeyDown}
        className="bg-bg-secondary border border-border-subtle shadow-2xl p-5 w-72 max-w-[calc(100vw-2rem)] animate-fade-in"
        style={{
          position: "fixed",
          bottom: "2rem",
          right: "2rem",
        }}
      >
        {/* Step indicator */}
        <p className="text-[10px] uppercase tracking-wider text-text-muted mb-2">
          Step {currentStep + 1} of {totalSteps}
        </p>

        {/* Step copy */}
        <p aria-live="polite" className="text-sm text-text-secondary leading-relaxed">
          {step?.copy}
        </p>

        {/* Controls row */}
        <div className="flex items-center justify-between mt-4">
          {/* Left: skip */}
          <button
            type="button"
            onClick={skipTour}
            className="text-xs text-text-muted hover:text-text-secondary"
          >
            Skip tour
          </button>

          {/* Right: back + next/done */}
          <div className="flex items-center">
            {!isFirstStep && (
              <button
                type="button"
                onClick={prevStep}
                className="text-sm text-text-secondary hover:text-text-primary mr-3"
              >
                Back
              </button>
            )}
            <button
              ref={primaryBtnRef}
              type="button"
              onClick={isLastStep ? skipTour : nextStep}
              className="bg-accent-cyan text-bg-primary font-bold px-4 py-2 text-sm min-h-11 hover:glow-cyan transition-shadow"
            >
              {isLastStep ? "Done" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
